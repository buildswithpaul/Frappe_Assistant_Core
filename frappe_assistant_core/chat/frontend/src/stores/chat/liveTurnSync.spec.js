import { describe, it, expect, vi } from "vitest";
import { reactive } from "vue";
import { applyLiveSnapshot, createLiveTurnSync, GAP_REREAD_MS } from "./liveTurnSync";

const ev = (seq, extra = {}) => ({ event: "stream_chunk", turn: "T1", seq, chunk: `c${seq}`, ...extra });

function harness({ snapshot = null, streaming = false } = {}) {
	const handled = [];
	const timers = [];
	const deps = {
		fetchSnapshot: vi.fn().mockResolvedValue(snapshot),
		onSnapshot: vi.fn(),
		onNoLiveTurn: vi.fn(),
		dispatch: (e) => handled.push(e),
		isStreaming: () => streaming,
		setTimer: (fn) => timers.push(fn),
		clearTimer: () => {},
	};
	const sync = createLiveTurnSync(deps);
	const deliver = (e) => sync.admit(e) && handled.push(e);
	return { sync, deps, handled, timers, deliver, setStreaming: (v) => (streaming = v) };
}

describe("applyLiveSnapshot", () => {
	const snap = {
		turn: "T1", seq: 5, message_id: "m1", text: "Hi",
		blocks: [{ type: "text", id: "t1", content: "Hi" }], active_thinking_id: null,
	};

	it("fills the placeholder row of the same turn", () => {
		const messages = reactive([{ role: "user", content: "q" }, { role: "assistant", message_id: "m1", content: "", blocks: [] }]);
		const msg = applyLiveSnapshot(messages, snap);
		expect(messages).toHaveLength(2);
		expect(msg.content).toBe("Hi");
		expect(msg.blocks).toEqual(snap.blocks);
		expect(msg.isStreaming).toBe(true);
	});

	it("adds a bubble when the user's message is last", () => {
		const messages = reactive([{ role: "user", content: "q" }]);
		const msg = applyLiveSnapshot(messages, { ...snap, message_id: null });
		expect(messages).toHaveLength(2);
		expect(msg.role).toBe("assistant");
		expect(msg.isStreaming).toBe(true);
	});

	it("adds a bubble rather than overwrite an earlier turn's answer", () => {
		const messages = reactive([{ role: "assistant", message_id: "old", content: "done" }, { role: "user", content: "q" }, { role: "assistant", message_id: "old2", content: "prev" }]);
		applyLiveSnapshot(messages, snap);
		expect(messages[2].content).toBe("prev");
		expect(messages).toHaveLength(4);
	});

	it("keeps the row's content when the snapshot has none yet (starting)", () => {
		const messages = reactive([{ role: "assistant", message_id: "m1", content: "First part", blocks: [{ type: "text", id: "a", content: "First part" }] }]);
		const msg = applyLiveSnapshot(messages, { ...snap, text: null, blocks: null });
		expect(msg.content).toBe("First part");
		expect(msg.isStreaming).toBe(true);
	});

	it("does not share block objects with the snapshot", () => {
		const messages = reactive([{ role: "user", content: "q" }]);
		const msg = applyLiveSnapshot(messages, snap);
		msg.blocks[0].content += "!";
		expect(snap.blocks[0].content).toBe("Hi");
	});
});

describe("createLiveTurnSync", () => {
	it("passes events without a turn straight through", () => {
		const h = harness();
		expect(h.sync.admit({ event: "stream_cancel_requested" })).toBe(true);
	});

	it("adopts the sending tab's own turn from its first event", () => {
		const h = harness({ streaming: true });
		expect(h.sync.admit(ev(1))).toBe(true);
		expect(h.sync.admit(ev(2))).toBe(true);
		expect(h.sync.admit(ev(2))).toBe(false); // duplicate
	});

	it("holds events while joining and replays only those after the snapshot", async () => {
		const h = harness({ snapshot: { turn: "T1", seq: 3 } });
		const joined = h.sync.join(async () => {
			h.deliver(ev(2));
			h.deliver(ev(4));
			h.deliver({ event: "stream_cancel_requested" });
		});
		expect(await joined).toBe(true);
		expect(h.deps.onSnapshot).toHaveBeenCalledWith({ turn: "T1", seq: 3 });
		expect(h.handled.map((e) => e.seq ?? "x")).toEqual([4, "x"]);
	});

	it("releases held events as before when no turn is running, and asks for a re-read after an end event", async () => {
		const h = harness({ snapshot: null });
		const joined = h.sync.join(async () => h.deliver(ev(9, { event: "stream_complete" })));
		expect(await joined).toBe(false);
		expect(h.handled).toHaveLength(1);
		expect(h.deps.onNoLiveTurn).toHaveBeenCalledWith({ sawTerminal: true });
	});

	it("joins a turn that started elsewhere", async () => {
		const h = harness({ snapshot: { turn: "T2", seq: 1 }, streaming: false });
		expect(h.sync.admit(ev(2, { turn: "T2" }))).toBe(false);
		await vi.waitFor(() => expect(h.deps.onSnapshot).toHaveBeenCalled());
		expect(h.handled.map((e) => e.seq)).toEqual([2]);
	});

	it("re-reads the snapshot after a gap, then replays what it had already shown past it", async () => {
		const h = harness({ streaming: true });
		h.deliver(ev(1));
		h.deliver(ev(4)); // 2 and 3 missed
		expect(h.timers).toHaveLength(1);
		h.deps.fetchSnapshot.mockResolvedValue({ turn: "T1", seq: 3 });
		await h.timers[0]();
		expect(h.deps.onSnapshot).toHaveBeenCalledWith({ turn: "T1", seq: 3 });
		expect(h.handled.map((e) => e.seq)).toEqual([1, 4, 4]);
	});

	it("waits the text-write interval before a gap re-read", () => {
		const setTimer = vi.fn();
		const sync = createLiveTurnSync({
			fetchSnapshot: vi.fn(), onSnapshot: vi.fn(), onNoLiveTurn: vi.fn(),
			dispatch: vi.fn(), isStreaming: () => true, setTimer, clearTimer: vi.fn(),
		});
		sync.admit(ev(1));
		sync.admit(ev(3));
		expect(setTimer).toHaveBeenCalledWith(expect.any(Function), GAP_REREAD_MS);
	});

	it("drops a join that a reset overtook", async () => {
		let release;
		const h = harness();
		h.deps.fetchSnapshot.mockReturnValue(new Promise((r) => (release = r)));
		const joined = h.sync.join();
		h.sync.reset();
		release({ turn: "T1", seq: 1 });
		expect(await joined).toBe(false);
		expect(h.deps.onSnapshot).not.toHaveBeenCalled();
	});

	it("releases held events and rethrows when the history read fails", async () => {
		const h = harness();
		const joined = h.sync.join(async () => {
			h.deliver({ event: "heartbeat" });
			throw new Error("offline");
		});
		await expect(joined).rejects.toThrow("offline");
		expect(h.handled).toHaveLength(1);
		expect(h.sync.admit({ event: "heartbeat" })).toBe(true);
	});
});
