import { describe, it, expect, vi } from "vitest";
import { reactive } from "vue";
import { applyLiveSnapshot, createLiveTurnSync, GAP_REREAD_MS } from "./liveTurnSync";

const ev = (seq, extra = {}) => ({ event: "stream_chunk", turn: "T1", seq, chunk: `c${seq}`, ...extra });

function harness({ snapshot = null, streaming = false, reloadHistory = undefined } = {}) {
	const handled = [];
	const timers = [];
	const deps = {
		fetchSnapshot: vi.fn().mockResolvedValue(snapshot),
		onSnapshot: vi.fn(),
		onNoLiveTurn: vi.fn(),
		dispatch: (e) => handled.push(e),
		isStreaming: () => streaming,
		reloadHistory,
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

	it("a turn begun elsewhere reloads history before showing the snapshot", async () => {
		const reloadHistory = vi.fn().mockResolvedValue();
		const h = harness({ snapshot: { turn: "T2", seq: 1 }, streaming: false, reloadHistory });
		expect(h.sync.admit(ev(2, { turn: "T2" }))).toBe(false);
		await vi.waitFor(() => expect(h.deps.onSnapshot).toHaveBeenCalled());
		expect(reloadHistory).toHaveBeenCalledTimes(1);
		expect(h.handled.map((e) => e.seq)).toEqual([2]);
	});

	it("a gap re-read does not call reloadHistory", async () => {
		const reloadHistory = vi.fn().mockResolvedValue();
		const h = harness({ streaming: true, reloadHistory });
		h.deliver(ev(1));
		h.deliver(ev(4)); // 2 and 3 missed
		expect(h.timers).toHaveLength(1);
		h.deps.fetchSnapshot.mockResolvedValue({ turn: "T1", seq: 3 });
		await h.timers[0]();
		expect(reloadHistory).not.toHaveBeenCalled();
	});

	it("replays only the snapshot's turn", async () => {
		const h = harness({ snapshot: { turn: "T3", seq: 3 } });
		const joined = h.sync.join(async () => {
			h.deliver(ev(9, { turn: "T1", event: "stream_complete" }));
			h.deliver(ev(4, { turn: "T3" }));
		});
		expect(await joined).toBe(true);
		expect(h.handled.map((e) => e.seq)).toEqual([4]);
		expect(h.deps.fetchSnapshot).toHaveBeenCalledTimes(1);
	});

	it("a turn with no snapshot stops asking", async () => {
		const h = harness({ snapshot: null });
		expect(h.sync.admit(ev(5, { turn: "T9" }))).toBe(false);
		await vi.waitFor(() => expect(h.deps.onNoLiveTurn).toHaveBeenCalled());
		expect(h.sync.admit(ev(6, { turn: "T9" }))).toBe(true);
		expect(h.deps.fetchSnapshot).toHaveBeenCalledTimes(1);
	});

	it("a failed reload is logged, not thrown", async () => {
		const reloadHistory = vi.fn().mockRejectedValue(new Error("offline"));
		const h = harness({ snapshot: null, streaming: false, reloadHistory });
		// Admit a foreign turn to trigger startJoin(reloadHistory), which should log but not throw
		h.sync.admit(ev(2, { turn: "T2" }));
		// Give the async join time to complete and log the error
		await new Promise((r) => setTimeout(r, 50));
		// The held event should have been released even though the join failed
		expect(h.handled.map((e) => e.seq)).toEqual([2]);
		// Verify no unhandled rejection by the test passing
	});
});
