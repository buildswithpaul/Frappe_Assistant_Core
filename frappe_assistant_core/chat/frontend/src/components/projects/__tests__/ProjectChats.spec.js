import { describe, it, expect, beforeAll, beforeEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";

const getSessions = vi.fn();
const createSession = vi.fn();
vi.mock("@/api/client", () => ({
	api: { chat: { getSessions: (...a) => getSessions(...a), createSession: (...a) => createSession(...a) } },
}));
const push = vi.fn();
vi.mock("vue-router", () => ({ useRouter: () => ({ push }) }));
const showError = vi.fn();
vi.mock("@/composables/useToast", () => ({ useToast: () => ({ showError }) }));

import ProjectChats from "@/components/projects/ProjectChats.vue";
import { useChatStore } from "@/stores/chatStore";

beforeAll(() => {
	window.__ = (s, args) => (args ? s.replace("{0}", args[0]) : s);
});

const ChatRowStub = { name: "ChatRow", props: { session: Object, showProject: Boolean, showTime: Boolean }, template: "<div data-test='chat-row' />" };

async function mountChats() {
	const pinia = createPinia();
	setActivePinia(pinia);
	const w = mount(ProjectChats, {
		props: { projectId: "p1", projectTitle: "Q3 Close" },
		global: { plugins: [pinia], stubs: { ChatRow: ChatRowStub } },
	});
	await flushPromises();
	return w;
}

const box = (w) => w.find("[data-test=project-chat-input]");
const sendBtn = (w) => w.find("[data-test=new-project-chat]");

beforeEach(() => {
	vi.clearAllMocks();
	getSessions.mockResolvedValue([]);
	createSession.mockResolvedValue({ session_id: "s9" });
});

describe("ProjectChats", () => {
	it("names the project in the chat box placeholder", async () => {
		const w = await mountChats();
		expect(box(w).attributes("placeholder")).toBe("Start a chat in Q3 Close…");
	});

	it("send starts a chat in the project, queues the text, and opens it", async () => {
		const w = await mountChats();
		await box(w).setValue("  What closes this week?  ");
		await sendBtn(w).trigger("click");
		await flushPromises();
		const store = useChatStore();
		expect(store.pendingProject).toEqual({ sessionId: "s9", projectId: "p1" });
		expect(store.takeFirstMessage("s9")).toBe("What closes this week?");
		expect(push).toHaveBeenCalledWith("/chat/s9");
		expect(box(w).element.value).toBe("");
	});

	it("keeps the text and shows an error when the chat cannot be created", async () => {
		// createSession swallows API errors and returns null — what a failed create looks like here.
		createSession.mockRejectedValue(new Error("down"));
		const w = await mountChats();
		await box(w).setValue("hello");
		await sendBtn(w).trigger("click");
		await flushPromises();
		expect(push).not.toHaveBeenCalled();
		expect(showError).toHaveBeenCalledTimes(1);
		expect(box(w).element.value).toBe("hello");
		expect(useChatStore().takeFirstMessage("s9")).toBe(null);
	});

	it("Enter sends, Shift+Enter does not", async () => {
		const w = await mountChats();
		await box(w).setValue("hello");
		await box(w).trigger("keydown", { key: "Enter", shiftKey: true });
		await flushPromises();
		expect(createSession).not.toHaveBeenCalled();
		await box(w).trigger("keydown", { key: "Enter" });
		await flushPromises();
		expect(createSession).toHaveBeenCalledTimes(1);
	});

	it("Enter during IME composition does not send", async () => {
		const w = await mountChats();
		await box(w).setValue("こんにちは");
		await box(w).trigger("keydown", { key: "Enter", isComposing: true });
		await flushPromises();
		expect(createSession).not.toHaveBeenCalled();
	});

	it("disables send while the box is empty", async () => {
		const w = await mountChats();
		expect(sendBtn(w).attributes("disabled")).toBeDefined();
		await box(w).setValue("hi");
		expect(sendBtn(w).attributes("disabled")).toBeUndefined();
	});

	it("loads the project's chats and lists them with time and without the project dot", async () => {
		getSessions.mockResolvedValue([{ session_id: "a", title: "One" }]);
		const w = await mountChats();
		expect(getSessions).toHaveBeenCalledWith({ limit: 100, project: "p1" });
		const row = w.findComponent(ChatRowStub);
		expect(row.props("showProject")).toBe(false);
		expect(row.props("showTime")).toBe(true);
		expect(w.find("[data-test=project-chats-count]").text()).toContain("1");
	});

	it("shows the empty state with no chats", async () => {
		const w = await mountChats();
		expect(w.find("[data-test=project-empty]").exists()).toBe(true);
	});
});
