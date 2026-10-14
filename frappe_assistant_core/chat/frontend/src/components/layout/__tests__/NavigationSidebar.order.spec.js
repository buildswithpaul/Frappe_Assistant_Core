import { describe, it, expect, beforeAll, beforeEach, vi } from "vitest";
import { nextTick } from "vue";
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import NavigationSidebar from "@/components/layout/NavigationSidebar.vue";

const route = vi.hoisted(() => ({ current: null }));
vi.mock("vue-router", async () => {
	const { reactive } = await import("vue");
	route.current = reactive({ path: "/chat", fullPath: "/chat" });
	return { useRoute: () => route.current };
});
vi.mock("@/api/client", () => ({ api: { chat: {}, projects: {} } }));
vi.mock("frappe-ui", () => ({ call: vi.fn().mockResolvedValue({}) }));

beforeAll(() => {
	window.__ = (s) => s;
});
beforeEach(() => {
	setActivePinia(createPinia());
	route.current.path = "/chat";
	route.current.fullPath = "/chat";
});

const ChatPanelStub = { name: "ChatPanel", template: "<div data-test='panel' />" };
const stubs = { NavRail: { template: "<nav data-test='rail' />" }, ChatPanel: ChatPanelStub };

function go(path) {
	route.current.path = path;
	route.current.fullPath = path;
	return nextTick();
}

describe("NavigationSidebar shell", () => {
	it("renders the rail before the chat panel", () => {
		const w = mount(NavigationSidebar, { global: { stubs } });
		const order = w.findAll("[data-test]").map((n) => n.attributes("data-test"));
		expect(order).toEqual(["rail", "panel"]);
	});

	it("shows the panel on chat and project routes only", async () => {
		const w = mount(NavigationSidebar, { global: { stubs } });
		for (const path of ["/", "/chat", "/chat/s1", "/chat/project/p1"]) {
			await go(path);
			expect(w.find("[data-test='panel']").exists(), path).toBe(true);
		}
		for (const path of ["/knowledge", "/agents", "/analytics", "/settings/profile"]) {
			await go(path);
			expect(w.find("[data-test='panel']").exists(), path).toBe(false);
			expect(w.find("[data-test='rail']").exists(), path).toBe(true);
		}
	});

	it("collapsed hides the panel and keeps the rail", () => {
		const w = mount(NavigationSidebar, { props: { collapsed: true }, global: { stubs } });
		expect(w.find("[data-test='panel']").exists()).toBe(false);
		expect(w.find("[data-test='rail']").exists()).toBe(true);
	});

	it("keeps the same panel instance between a chat and a project page", async () => {
		const w = mount(NavigationSidebar, { global: { stubs } });
		const before = w.findComponent(ChatPanelStub).vm;
		await go("/chat/project/p1");
		await go("/chat/s1");
		expect(w.findComponent(ChatPanelStub).vm).toBe(before);
	});

	it("sizes the drawer to the rail when there is no panel to show", async () => {
		const w = mount(NavigationSidebar, { global: { stubs } });
		expect(w.find("aside").classes()).toContain("has-panel");
		await go("/knowledge");
		expect(w.find("aside").classes()).not.toContain("has-panel");
	});
});
