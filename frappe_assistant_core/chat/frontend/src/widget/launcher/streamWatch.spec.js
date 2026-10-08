import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { startStreamWatch } from "./streamWatch.js";

describe("stream watch", () => {
	let handlers, realtime, sid, mounted, ensurePanel, onApproval, stop;

	const start = () => {
		stop = startStreamWatch({ getSessionId: () => sid, isMounted: () => mounted, ensurePanel, onApproval });
	};

	beforeEach(() => {
		handlers = {};
		sid = "s1";
		mounted = false;
		ensurePanel = vi.fn(async () => {});
		onApproval = vi.fn();
		// Desk's realtime client once its socket exists (the watch waits for it, as browserTools does).
		realtime = {
			socket: {},
			on: vi.fn((name, fn) => (handlers[name] = fn)),
			off: vi.fn(),
			task_subscribe: vi.fn(),
		};
		window.frappe = { realtime };
	});

	afterEach(() => {
		if (stop) stop();
		delete window.frappe;
	});

	it("subscribes to the session room and mounts the panel once for the first event", () => {
		start();
		expect(realtime.task_subscribe).toHaveBeenCalledWith("s1");
		handlers.faco_message_stream({ session_id: "s1", event: "stream_start" });
		handlers.faco_message_stream({ session_id: "s1", event: "thinking" });
		expect(ensurePanel).toHaveBeenCalledTimes(1);
		expect(onApproval).not.toHaveBeenCalled();
	});

	it("raises attention for an approval that arrives before the panel exists", () => {
		start();
		const event = { session_id: "s1", event: "approval_required", tool_name: "delete_document" };
		handlers.faco_message_stream(event);
		expect(ensurePanel).toHaveBeenCalledTimes(1);
		expect(onApproval).toHaveBeenCalledWith(event);
	});

	it("treats an AR interrupt event for this session the same way", () => {
		start();
		handlers.ar_interrupt_event({ session_id: "s1", kind: "resolved" });
		expect(ensurePanel).toHaveBeenCalledTimes(1);
	});

	it("ignores another session's events", () => {
		start();
		handlers.faco_message_stream({ session_id: "other", event: "approval_required" });
		handlers.ar_interrupt_event({ session_id: "other", kind: "expired" });
		expect(ensurePanel).not.toHaveBeenCalled();
		expect(onApproval).not.toHaveBeenCalled();
	});

	it("does nothing once the panel is mounted: its own useStreaming handles events", () => {
		mounted = true;
		start();
		handlers.faco_message_stream({ session_id: "s1", event: "approval_required" });
		expect(ensurePanel).not.toHaveBeenCalled();
		expect(onApproval).not.toHaveBeenCalled();
	});

	it("re-subscribes when the session changes", () => {
		start();
		sid = "s2";
		stop.resubscribe();
		expect(realtime.task_subscribe).toHaveBeenLastCalledWith("s2");
	});

	it("detaches its listeners when stopped, without leaving the room the panel may share", () => {
		start();
		stop();
		expect(realtime.off).toHaveBeenCalledWith("faco_message_stream", handlers.faco_message_stream);
		expect(realtime.off).toHaveBeenCalledWith("ar_interrupt_event", handlers.ar_interrupt_event);
		expect(realtime.task_unsubscribe).toBeUndefined();
	});
});
