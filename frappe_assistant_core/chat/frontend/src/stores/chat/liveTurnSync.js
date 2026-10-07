// Joining a turn that is already running: the server keeps a snapshot of it
// (get_live_turn) and numbers every streamed event with {turn, seq}. A surface
// that opens the conversation mid-turn holds incoming events, shows the
// snapshot as a live bubble, then applies only the events numbered after it.
import { carryCardDecisions, findActiveMessage } from "./utils";
import { logger } from "@/utils/logger";

// Text is written to the snapshot at most every 500ms server-side; a re-read
// after this long always covers a gap.
export const GAP_REREAD_MS = 600;
// Enough to replay what a re-read's snapshot is behind by.
export const RECENT_EVENTS_MAX = 300;
const TERMINAL_EVENTS = new Set(["stream_complete", "stream_error", "stream_aborted"]);

export function applyLiveSnapshot(messages, snap) {
	const last = findActiveMessage(messages);
	// A streaming row is the snapshot's unless it already carries another turn's id.
	const otherAnswer = snap.message_id && last?.message_id && last.message_id !== snap.message_id;
	const sameTurn =
		last?.role === "assistant" &&
		((last.isStreaming && !otherAnswer) || (snap.message_id && last.message_id === snap.message_id));
	if (!sameTurn) {
		messages.push({ role: "assistant", content: "", blocks: [], timestamp: new Date().toISOString() });
	}
	// The reactive element, not the pushed literal.
	const msg = sameTurn ? last : messages[messages.length - 1];
	if (snap.message_id) msg.message_id = snap.message_id;
	// A snapshot taken before the user decided a card still holds it pending.
	if (Array.isArray(snap.blocks)) msg.blocks = carryCardDecisions(msg.blocks, structuredClone(snap.blocks));
	if (typeof snap.text === "string") msg.content = snap.text;
	msg.isStreaming = true;
	return msg;
}

export function createLiveTurnSync({
	fetchSnapshot,
	onSnapshot,
	onNoLiveTurn,
	dispatch,
	ownClientTurn,
	reloadHistory,
	setTimer = setTimeout,
	clearTimer = clearTimeout,
}) {
	let turn = null;
	let lastSeq = null;
	let joining = false;
	let joinId = 0;
	let gapTimer = null;
	let held = [];
	const recent = [];
	const settledTurns = [];
	// Own turns this surface moved on from. Approving a card starts the resume
	// as a new turn whose first event can arrive while the paused turn is still
	// streaming under the old client id; those late events stay this surface's.
	const previousOwnTurns = [];

	function settle(events) {
		for (const e of events) {
			if (e.turn != null && !settledTurns.includes(e.turn)) {
				settledTurns.push(e.turn);
				if (settledTurns.length > 20) settledTurns.shift();
			}
		}
	}

	function remember(event) {
		recent.push(event);
		if (recent.length > RECENT_EVENTS_MAX) recent.shift();
	}

	function cancelGap() {
		if (gapTimer) clearTimer(gapTimer);
		gapTimer = null;
	}

	function scheduleGap() {
		if (gapTimer) return;
		gapTimer = setTimer(() => {
			gapTimer = null;
			return startJoin();
		}, GAP_REREAD_MS);
	}

	function startJoin(prepare) {
		return join(prepare).catch((err) => logger.warn("Live turn join failed:", err));
	}

	function admit(event) {
		if (joining) {
			held.push(event);
			return false;
		}
		if (event.turn == null || event.seq == null) return true;
		if (event.turn !== turn) {
			if (settledTurns.includes(event.turn)) return true;
			if (previousOwnTurns.includes(event.turn)) {
				if (TERMINAL_EVENTS.has(event.event)) settle([event]);
				return true;
			}
			if (event.client_turn == null || event.client_turn !== ownClientTurn()) {
				// A turn this surface did not send: catch up before showing it.
				held.push(event);
				startJoin(reloadHistory);
				return false;
			}
			if (turn != null) {
				previousOwnTurns.push(turn);
				if (previousOwnTurns.length > 5) previousOwnTurns.shift();
			}
			turn = event.turn;
			lastSeq = null;
			recent.length = 0;
		}
		if (lastSeq !== null && event.seq <= lastSeq) return false;
		if (lastSeq !== null && event.seq > lastSeq + 1) scheduleGap();
		lastSeq = event.seq;
		remember(event);
		if (TERMINAL_EVENTS.has(event.event)) {
			// Whatever of this turn still arrives is late, not a new turn to adopt.
			settle([event]);
			turn = null;
			lastSeq = null;
			recent.length = 0;
		}
		return true;
	}

	function release(events) {
		for (const event of events) dispatch(event);
	}

	async function join(prepare) {
		const id = ++joinId;
		joining = true;
		cancelGap();
		let snap = null;
		try {
			[, snap] = await Promise.all([
				prepare ? prepare() : null,
				// A failed read (even a synchronous throw) means "no live turn": behave as before.
				Promise.resolve().then(fetchSnapshot).catch(() => null),
			]);
		} catch (err) {
			if (id === joinId) {
				joining = false;
				const pending = held;
				held = [];
				// The failure may last: let these events through rather than re-join on each.
				settle(pending);
				release(pending);
			}
			throw err;
		}
		if (id !== joinId) return false;
		joining = false;
		const pending = held;
		held = [];
		if (!snap) {
			turn = null;
			lastSeq = null;
			recent.length = 0;
			settle(pending);
			release(pending);
			onNoLiveTurn({ sawTerminal: pending.some((e) => TERMINAL_EVENTS.has(e.event)) });
			return false;
		}
		turn = snap.turn;
		lastSeq = snap.seq;
		onSnapshot(snap);
		const shownPastSnapshot = recent.filter((e) => e.turn === snap.turn && e.seq > snap.seq);
		recent.length = 0;
		const toReplay = [...shownPastSnapshot, ...pending].filter((e) => e.turn == null || e.turn === snap.turn);
		for (const event of toReplay) {
			if (admit(event)) dispatch(event);
		}
		return true;
	}

	function reset() {
		joinId++;
		joining = false;
		turn = null;
		lastSeq = null;
		held = [];
		recent.length = 0;
		settledTurns.length = 0;
		previousOwnTurns.length = 0;
		cancelGap();
	}

	return { admit, join, reset };
}
