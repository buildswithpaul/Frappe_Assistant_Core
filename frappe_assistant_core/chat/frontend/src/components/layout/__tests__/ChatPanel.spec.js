import { describe, it, expect, beforeAll, beforeEach, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import ChatPanel from "@/components/layout/ChatPanel.vue";

vi.mock("@/api/client", () => ({ api: { chat: {}, projects: {} } }));
vi.mock("frappe-ui", () => ({ call: vi.fn().mockResolvedValue({}) }));

beforeAll(() => {
	window.__ = (s) => s;
});
beforeEach(() => setActivePinia(createPinia()));

const stubs = {
	ProjectsSection: { template: "<div data-test='projects' />" },
	ConversationsList: { template: "<div data-test='recents' />" },
	ConversationSearch: { template: "<div data-test='search' />" },
};

describe("ChatPanel", () => {
	it("renders New chat, search, projects and recents in that order", () => {
		const w = mount(ChatPanel, { props: { showNewChat: true }, global: { stubs } });
		const order = w
			.findAll("[data-test]")
			.map((n) => n.attributes("data-test"))
			.filter((t) => ["new-chat", "search", "projects", "recents"].includes(t));
		expect(order).toEqual(["new-chat", "search", "projects", "recents"]);
	});

	it("emits new-chat from the New chat button", async () => {
		const w = mount(ChatPanel, { props: { showNewChat: true }, global: { stubs } });
		await w.find("[data-test='new-chat']").trigger("click");
		expect(w.emitted("new-chat")).toHaveLength(1);
	});

	it("hides New chat until the user is set up", () => {
		const w = mount(ChatPanel, { props: { showNewChat: false }, global: { stubs } });
		expect(w.find("[data-test='new-chat']").exists()).toBe(false);
	});
});
