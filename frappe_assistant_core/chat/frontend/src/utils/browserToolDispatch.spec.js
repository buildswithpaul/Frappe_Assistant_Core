import { describe, it, expect, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import {
	ACK_METHOD,
	BROWSER_TOOL_CALL_EVENT,
	PENDING_METHOD,
	RESULT_METHOD,
	createDispatcher,
} from "./browserToolDispatch.js";

const DECLINED = /declined/;

function setup({ confirm = async () => "approve", ack = async () => null, ...options } = {}) {
	const calls = [];
	const listeners = {};
	const unsubscribe = vi.fn();
	const transport = {
		on: vi.fn((event, fn) => {
			listeners[event] = fn;
			return unsubscribe;
		}),
		call: vi.fn((method, args) => {
			calls.push({ name: method.split(".").pop(), args });
			if (method === ACK_METHOD) return ack();
			if (method === PENDING_METHOD) return Promise.resolve(options.pending || []);
			return Promise.resolve(null);
		}),
	};
	const handlers = {
		take_screenshot: vi.fn(async () => ({ success: true })),
		get_page_context: vi.fn(async () => ({ page_type: "x" })),
	};
	const dispatcher = createDispatcher({
		transport,
		handlers,
		confirm: vi.fn(confirm),
		getSessionId: () => "s1",
		confirmTools: new Set(["take_screenshot"]),
		retryDelayMs: 0,
		...options,
	});
	const sequence = () => calls.map((c) => (c.name === "submit_browser_tool_ack" ? c.args.state : c.name));
	const submits = () => calls.filter((c) => c.name === "submit_browser_tool_result");
	return { dispatcher, transport, handlers, listeners, unsubscribe, calls, sequence, submits };
}

const shot = (call_id, extra = {}) => ({ call_id, tool_name: "take_screenshot", params: {}, ...extra });

describe("createDispatcher", () => {
	it("drops a call addressed to another session: no ack, no prompt, no result", async () => {
		const t = setup();
		await t.dispatcher.handle(shot("o1", { session_id: "other" }));
		expect(t.calls).toEqual([]);
		expect(t.handlers.take_screenshot).not.toHaveBeenCalled();
	});

	it("answers a call for its own session, or one with no session", async () => {
		const t = setup();
		await t.dispatcher.handle(shot("m1", { session_id: "s1" }));
		await t.dispatcher.handle(shot("m2"));
		expect(t.handlers.take_screenshot).toHaveBeenCalledTimes(2);
	});

	it("runs a call delivered twice (socket and pending queue) once", async () => {
		const t = setup();
		await t.dispatcher.handle(shot("d1"));
		await t.dispatcher.handle(shot("d1"));
		expect(t.handlers.take_screenshot).toHaveBeenCalledTimes(1);
		expect(t.submits()).toHaveLength(1);
	});

	it("acks received, awaiting_user and executing in order, then submits the result", async () => {
		const t = setup();
		await t.dispatcher.handle(shot("a1"));
		expect(t.sequence()).toEqual(["received", "awaiting_user", "executing", "submit_browser_tool_result"]);
		expect(t.submits()[0].args).toEqual({ call_id: "a1", result: { success: true } });
	});

	it("asks for confirmation only after reporting awaiting_user", async () => {
		const t = setup();
		let seenAtPrompt;
		t.dispatcher = createDispatcher({
			transport: t.transport,
			handlers: t.handlers,
			getSessionId: () => "s1",
			confirmTools: new Set(["take_screenshot"]),
			confirm: async () => {
				seenAtPrompt = t.sequence();
				return "approve";
			},
		});
		await t.dispatcher.handle(shot("a2"));
		expect(seenAtPrompt).toEqual(["received", "awaiting_user"]);
	});

	it("skips awaiting_user for a tool that needs no confirmation", async () => {
		const t = setup();
		await t.dispatcher.handle({ call_id: "n1", tool_name: "get_page_context", params: {} });
		expect(t.sequence()).toEqual(["received", "executing", "submit_browser_tool_result"]);
	});

	it("never waits on an ack: a hung ack still lets the tool run", async () => {
		const t = setup({ ack: () => new Promise(() => {}) });
		await t.dispatcher.handle(shot("h1"));
		expect(t.handlers.take_screenshot).toHaveBeenCalledTimes(1);
		expect(t.submits()).toHaveLength(1);
	});

	it("returns an error and runs nothing when the user declines", async () => {
		const t = setup({ confirm: async () => "deny" });
		await t.dispatcher.handle(shot("x1"));
		expect(t.handlers.take_screenshot).not.toHaveBeenCalled();
		expect(t.submits()[0].args.error).toMatch(DECLINED);
		expect(t.submits()[0].args.result).toBeUndefined();
	});

	it("denies when the prompt throws", async () => {
		const t = setup({
			confirm: async () => {
				throw new Error("card crashed");
			},
		});
		await t.dispatcher.handle(shot("x2"));
		expect(t.handlers.take_screenshot).not.toHaveBeenCalled();
		expect(t.submits()[0].args.error).toMatch(DECLINED);
	});

	it.each([undefined, null, "rejected", "Approve", ""])("denies on the unexpected decision %j", async (decision) => {
		const t = setup({ confirm: async () => decision });
		await t.dispatcher.handle(shot("x3"));
		expect(t.handlers.take_screenshot).not.toHaveBeenCalled();
	});

	it("does not ask again for a tool the user trusted", async () => {
		const t = setup({ confirm: async () => "trust" });
		await t.dispatcher.handle(shot("t1"));
		await t.dispatcher.handle(shot("t2"));
		expect(t.handlers.take_screenshot).toHaveBeenCalledTimes(2);
		expect(t.sequence().filter((s) => s === "awaiting_user")).toHaveLength(1);
	});

	it("submits a preflight error without asking the user", async () => {
		const t = setup({ preflight: () => "No page is open in the panel." });
		await t.dispatcher.handle(shot("p1"));
		expect(t.sequence()).toEqual(["received", "submit_browser_tool_result"]);
		expect(t.submits()[0].args.error).toBe("No page is open in the panel.");
		expect(t.handlers.take_screenshot).not.toHaveBeenCalled();
	});

	it("submits a handler's error, and an unknown tool, as errors", async () => {
		const t = setup();
		t.handlers.take_screenshot.mockResolvedValueOnce({ error: "boom" });
		await t.dispatcher.handle(shot("e1"));
		await t.dispatcher.handle({ call_id: "e2", tool_name: "navigate_to", params: {} });
		expect(t.submits().map((s) => s.args.error)).toEqual(["boom", "Unknown browser tool: navigate_to"]);
	});

	it("retries a failed submit", async () => {
		const t = setup();
		let failures = 2;
		const call = t.transport.call.getMockImplementation();
		t.transport.call.mockImplementation((method, args) => {
			if (method === RESULT_METHOD && failures-- > 0) {
				call(method, args);
				return Promise.reject(new Error("network"));
			}
			return call(method, args);
		});
		await t.dispatcher.handle(shot("r1"));
		expect(t.submits()).toHaveLength(3);
	});

	it("listens once started and goes inert once stopped", async () => {
		const t = setup();
		t.dispatcher.start();
		expect(t.transport.on).toHaveBeenCalledWith(BROWSER_TOOL_CALL_EVENT, expect.any(Function));
		await t.listeners[BROWSER_TOOL_CALL_EVENT](shot("l1"));
		t.dispatcher.stop();
		await t.listeners[BROWSER_TOOL_CALL_EVENT](shot("l2"));
		expect(t.handlers.take_screenshot).toHaveBeenCalledTimes(1);
		expect(t.unsubscribe).toHaveBeenCalledTimes(1);
	});

	it("leaves a call it does not own alone: no ack, no prompt, no result", async () => {
		const t = setup({ ownsCall: (call) => call.client_type === "spa" });
		await t.dispatcher.handle(shot("w1", { client_type: "widget" }));
		expect(t.calls).toEqual([]);
		await t.dispatcher.handle(shot("w2", { client_type: "spa" }));
		expect(t.handlers.take_screenshot).toHaveBeenCalledTimes(1);
	});

	it("can leave a tool it has no handler for unanswered", async () => {
		const t = setup({ ignoreUnknownTools: true });
		await t.dispatcher.handle({ call_id: "u1", tool_name: "get_form_data", params: {} });
		expect(t.calls).toEqual([]);
	});

	it("scopes Always Allow by its trust key", async () => {
		let page = "a";
		const t = setup({ confirm: async () => "trust", trustKey: (tool) => `${page}|${tool}` });
		await t.dispatcher.handle(shot("k1"));
		await t.dispatcher.handle(shot("k2"));
		page = "b";
		await t.dispatcher.handle(shot("k3"));
		expect(t.sequence().filter((s) => s === "awaiting_user")).toHaveLength(2);
	});

	it("denies a confirmation still open when it stops", async () => {
		const t = setup({ confirm: () => new Promise(() => {}) });
		const pending = t.dispatcher.handle(shot("s1"));
		await Promise.resolve();
		t.dispatcher.stop();
		await pending;
		expect(t.handlers.take_screenshot).not.toHaveBeenCalled();
		expect(t.submits()[0].args.error).toMatch(DECLINED);
	});

	it("drains this session's pending calls", async () => {
		const t = setup({ pending: [shot("q1"), shot("q2")] });
		await t.dispatcher.drainPending();
		expect(t.calls[0]).toEqual({ name: "get_pending_browser_tool_calls", args: { session_id: "s1" } });
		expect(t.handlers.take_screenshot).toHaveBeenCalledTimes(2);
	});
});

describe("bridge endpoints", () => {
	const bridge = readFileSync(resolve(process.cwd(), "../../plugins/faco/tools/browser_bridge.py"), "utf8");

	it.each([ACK_METHOD, RESULT_METHOD, PENDING_METHOD])("%s is a POST endpoint the server exposes", (method) => {
		expect(method).toMatch(/^frappe_assistant_core\.plugins\.faco\.tools\.browser_bridge\./);
		const name = method.split(".").pop();
		expect(bridge).toMatch(new RegExp(`@frappe\\.whitelist\\(methods=\\["POST"\\]\\)\\ndef ${name}\\(`));
	});
});
