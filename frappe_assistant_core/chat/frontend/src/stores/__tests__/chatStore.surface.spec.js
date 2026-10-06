import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useChatStore } from "@/stores/chatStore";
import { configureSurface, resetSurface } from "@/stores/chat/surface";
import { api } from "@/api/client";
import { call } from "frappe-ui";

vi.mock("@/api/client", () => ({
	api: {
		chat: {
			getMessages: vi.fn(),
			cancelStream: vi.fn().mockResolvedValue({}),
			send: vi.fn().mockResolvedValue({}),
			continueResponse: vi.fn().mockResolvedValue({}),
		},
	},
}));
vi.mock("frappe-ui", () => ({ call: vi.fn().mockResolvedValue({}) }));

const sentOptions = () => api.chat.send.mock.calls[0][7];
const sentModel = () => api.chat.send.mock.calls[0][4];
const resumePayload = () => call.mock.calls.find(([m]) => m.endsWith("resume_interrupt"))[1];

// Same card ask_user persists with (see chatStore.pendingInteraction.spec.js).
const pendingCard = () => ({
	type: "interaction",
	id: "blk1",
	status: "pending",
	interactionType: "text_input",
	interrupts: [{ id: "int1" }],
});

describe("surface config", () => {
	let store;
	beforeEach(() => {
		setActivePinia(createPinia());
		localStorage.clear();
		vi.clearAllMocks();
		store = useChatStore();
		store.currentSessionId = "s1";
	});
	afterEach(() => resetSurface());

	it("FAC Chat keeps sending as spa", async () => {
		await store.sendMessage("hi", [], null, "m1");
		expect(sentOptions().client_type).toBe("spa");
		expect(sentModel()).toBe("m1");
	});

	it("the widget sends client_type widget, which is what enables browser tools", async () => {
		configureSurface({ name: "widget", clientType: "widget", modelId: "auto" });
		await store.sendMessage("hi", [], null, null);
		expect(sentOptions().client_type).toBe("widget");
		expect(sentModel()).toBe("auto");
	});

	it("the widget attaches diagnostics counts when there are any", async () => {
		configureSurface({ clientType: "widget", clientSignals: () => '{"recent_errors":{"console":2}}' });
		await store.sendMessage("hi", [], null, null);
		expect(sentOptions().client_signals).toBe('{"recent_errors":{"console":2}}');
	});

	it("sends no client_signals when the provider has nothing", async () => {
		configureSurface({ clientType: "widget", clientSignals: () => null });
		await store.sendMessage("hi", [], null, null);
		expect(sentOptions()).not.toHaveProperty("client_signals");
	});

	it("a continue keeps the widget's client_type", async () => {
		configureSurface({ clientType: "widget" });
		store.messages.push({ role: "assistant", message_id: "m-1", content: "half", blocks: [] });
		await store.continueMessage("m-1");
		expect(api.chat.continueResponse.mock.calls[0][2].client_type).toBe("widget");
	});

	it("a resume keeps the widget's client_type — without it AR rebuilds the paused agent", async () => {
		configureSurface({ clientType: "widget" });
		store.messages = [{ role: "assistant", isStreaming: true, message_id: "m-1", blocks: [pendingCard()] }];
		await store.submitInterruptDecision({
			blockId: "blk1",
			resolution: "answered",
			userResponse: "Tony Stark",
			response: "Tony Stark",
		});
		expect(resumePayload().client_type).toBe("widget");
	});

	it("a resume from FAC Chat stays spa", async () => {
		store.messages = [{ role: "assistant", isStreaming: true, message_id: "m-1", blocks: [pendingCard()] }];
		await store.submitInterruptDecision({
			blockId: "blk1",
			resolution: "answered",
			userResponse: "x",
			response: "x",
		});
		expect(resumePayload().client_type).toBe("spa");
	});
});
