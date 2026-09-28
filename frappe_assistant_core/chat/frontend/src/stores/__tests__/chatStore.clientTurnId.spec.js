import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useChatStore } from "@/stores/chatStore";
import { api } from "@/api/client";

// FAC clears a session's cancel flag when it accepts a send, Continue
// or resume, so a Stop that reached FAC while that request was still
// on its way was erased by the request's own accept. Each request now carries a
// client turn id, the bubble keeps it as _requestId, and a Stop names it: FAC
// keeps a Stop that names the request it is accepting.
vi.mock("@/api/client", () => ({
	api: { chat: { send: vi.fn(), continueResponse: vi.fn(), cancelStream: vi.fn() } },
}));
vi.mock("frappe-ui", () => ({ call: vi.fn() }));

// A POST FAC has not answered yet.
const onItsWay = () => new Promise(() => {});

describe("a Stop names the request it stops", () => {
	let store, call;

	beforeEach(async () => {
		setActivePinia(createPinia());
		localStorage.clear();
		vi.clearAllMocks();
		({ call } = await import("frappe-ui"));
		api.chat.cancelStream.mockResolvedValue({});
		store = useChatStore();
		store.currentSessionId = "s1";
	});

	it("sends a send's id with send_message, and a Stop while the send is on its way names it", async () => {
		api.chat.send.mockReturnValue(onItsWay());
		store.sendMessage("Summarise the overdue invoices", [], null, "m1");

		await store.abortStream();

		const sent = api.chat.send.mock.calls[0][7].client_turn_id;
		expect(sent).toEqual(expect.any(String));
		expect(sent).toBe(store.messages.at(-1)._requestId);
		expect(api.chat.cancelStream).toHaveBeenCalledWith("s1", sent, sent);
	});

	it("gives every send an id of its own", async () => {
		api.chat.send.mockResolvedValue({});
		await store.sendMessage("First question", [], null, "m1");
		store.completeStreaming("One.", {});
		await store.sendMessage("Second question", [], null, "m1");

		const [first, second] = api.chat.send.mock.calls.map((args) => args[7].client_turn_id);
		expect(second).toEqual(expect.any(String));
		expect(second).not.toBe(first);
	});

	it("sends a Continue's own id, and a Stop while the Continue is on its way names it", async () => {
		api.chat.continueResponse.mockReturnValue(onItsWay());
		store.messages.push({
			role: "assistant",
			message_id: "msg-42",
			content: "partial",
			truncated: true,
			isStreaming: false,
			blocks: [],
			_requestId: "the-send-that-was-cut",
		});
		store.continueMessage("msg-42");

		await store.abortStream();

		const continued = api.chat.continueResponse.mock.calls[0][2].client_turn_id;
		expect(continued).toEqual(expect.any(String));
		expect(continued).not.toBe("the-send-that-was-cut");
		expect(api.chat.cancelStream).toHaveBeenCalledWith("s1", continued, continued);
	});

	it("sends a resume's own id with resume_interrupt, and a Stop once it streams names it", async () => {
		call.mockResolvedValue({});
		store.messages = [
			{
				role: "assistant",
				message_id: "msg-7",
				_requestId: "the-send-that-paused",
				blocks: [
					{
						type: "interaction",
						id: "blk1",
						status: "pending",
						interactionType: "text_input",
						interrupts: [{ id: "int1" }],
					},
				],
			},
		];
		await store.answerPendingQuestion("Acme Ltd");

		// The SPA shows Stop again only once the resumed stream_start arrives.
		store.handleStreamResumed();
		await store.abortStream();

		const resumed = call.mock.calls[0][1].client_turn_id;
		expect(resumed).toEqual(expect.any(String));
		expect(resumed).not.toBe("the-send-that-paused");
		expect(api.chat.cancelStream).toHaveBeenCalledWith("s1", resumed, resumed);
	});

	it("names no request when the turn has none (a turn loaded from history)", async () => {
		store.messages = [{ role: "assistant", content: "Working…", isStreaming: true, blocks: [] }];
		store.isStreaming = true;

		await store.abortStream();

		expect(api.chat.cancelStream).toHaveBeenCalledWith("s1", null, null);
	});
});
