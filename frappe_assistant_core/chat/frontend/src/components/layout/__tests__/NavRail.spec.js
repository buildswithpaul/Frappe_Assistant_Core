import { describe, it, expect, beforeAll, beforeEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createRouter, createMemoryHistory } from "vue-router";
import NavRail from "@/components/layout/NavRail.vue";
import { usePagesStore } from "@/stores/pagesStore";
import { useUserStore } from "@/stores/userStore";

vi.mock("@/api/domains/facPage", () => ({
	facPage: { listPages: vi.fn().mockResolvedValue([]), getPage: vi.fn() },
}));
vi.mock("@/api/_core", () => ({ baseCall: vi.fn(), getCall: vi.fn() }));

beforeAll(() => {
	window.__ = (s) => s;
});

const Blank = { template: "<div />" };

async function mountRail({ path = "/chat", props = {}, user = {}, pages = [] } = {}) {
	const pinia = createPinia();
	setActivePinia(pinia);
	Object.assign(useUserStore(), { memoryEnabled: true, workflowsEnabled: true, isAdmin: true, ...user });
	// The list is loaded after boot (NavRail asks the store); seeded here as that load's result.
	Object.assign(usePagesStore(), { pages, loaded: true });
	const router = createRouter({
		history: createMemoryHistory(),
		routes: ["/", "/chat", "/chat/:id", "/chat/project/:projectId", "/knowledge", "/agents", "/pages", "/pages/:name", "/analytics", "/settings"].map((p) => ({
			path: p,
			component: Blank,
		})),
	});
	router.push(path);
	await router.isReady();
	const wrapper = mount(NavRail, {
		props: { panelCollapsed: false, ...props },
		global: { plugins: [pinia, router], stubs: { FacoRobot: true, UserDropdown: { template: "<div data-test='user-menu' />" } } },
	});
	await flushPromises();
	wrapper.router = router;
	return wrapper;
}

const item = (w, name) => w.find(`[data-test="rail-${name}"]`);

describe("NavRail", () => {
	beforeEach(() => setActivePinia(createPinia()));

	it("hides Knowledge Base without the memory app and Agents without workflows", async () => {
		const w = await mountRail({ user: { memoryEnabled: false, workflowsEnabled: false } });
		expect(item(w, "knowledge").exists()).toBe(false);
		expect(item(w, "agents").exists()).toBe(false);
		expect(item(w, "chat").exists()).toBe(true);
	});

	it("hides Usage from non-admins", async () => {
		const w = await mountRail({ user: { isAdmin: false } });
		expect(item(w, "usage").exists()).toBe(false);
	});

	it("marks only the item for the current route active", async () => {
		const w = await mountRail({ path: "/knowledge" });
		expect(item(w, "knowledge").classes()).toContain("active");
		expect(item(w, "chat").classes()).not.toContain("active");
	});

	it("marks Chat active on a project page", async () => {
		const w = await mountRail({ path: "/chat/project/p1" });
		expect(item(w, "chat").classes()).toContain("active");
	});

	it("renders the user menu", async () => {
		const w = await mountRail();
		expect(w.find("[data-test='user-menu']").exists()).toBe(true);
	});

	it("emits return-to-desk from the Desk item", async () => {
		const w = await mountRail();
		await item(w, "desk").trigger("click");
		expect(w.emitted("return-to-desk")).toHaveLength(1);
	});

	it("clicking Chat while the panel is collapsed emits toggle-sidebar", async () => {
		const w = await mountRail({ props: { panelCollapsed: true } });
		await item(w, "chat").trigger("click");
		expect(w.emitted("toggle-sidebar")).toHaveLength(1);
	});

	it("reopening the collapsed panel keeps the current chat or project page", async () => {
		const w = await mountRail({ path: "/chat/project/p1", props: { panelCollapsed: true } });
		await item(w, "chat").trigger("click");
		await flushPromises();
		expect(w.emitted("toggle-sidebar")).toHaveLength(1);
		expect(w.router.currentRoute.value.fullPath).toBe("/chat/project/p1");
	});

	it("Chat navigates to /chat from another area even when the panel is collapsed", async () => {
		const w = await mountRail({ path: "/knowledge", props: { panelCollapsed: true } });
		await item(w, "chat").trigger("click");
		await flushPromises();
		expect(w.router.currentRoute.value.fullPath).toBe("/chat");
	});

	it("clicking Chat with the panel open does not toggle it", async () => {
		const w = await mountRail();
		await item(w, "chat").trigger("click");
		expect(w.emitted("toggle-sidebar")).toBeUndefined();
	});

	it("shows Pages only when the user can open a page, right after Agents", async () => {
		expect(item(await mountRail({ pages: [] }), "pages").exists()).toBe(false);
		const w = await mountRail({ pages: [{ name: "costs-a1b2c3" }] });
		expect(item(w, "pages").attributes("href")).toBe("/pages");
		const order = w.findAll(".rail-item").map((i) => i.attributes("data-test"));
		expect(order.indexOf("rail-pages")).toBe(order.indexOf("rail-agents") + 1);
	});

	it("shows Pages when Agents is hidden, after the last item before it", async () => {
		const w = await mountRail({ user: { workflowsEnabled: false }, pages: [{ name: "x" }] });
		const order = w.findAll(".rail-item").map((i) => i.attributes("data-test"));
		expect(order.indexOf("rail-pages")).toBe(order.indexOf("rail-knowledge") + 1);
	});

	it("marks Pages active on a page route", async () => {
		const w = await mountRail({ path: "/pages/x", pages: [{ name: "x" }] });
		expect(item(w, "pages").classes()).toContain("active");
	});

	it("gives every item an aria-label and a title", async () => {
		const w = await mountRail({ pages: [{ name: "x" }] });
		for (const name of ["chat", "knowledge", "agents", "pages", "usage", "desk"]) {
			expect(item(w, name).attributes("aria-label"), name).toBeTruthy();
			expect(item(w, name).attributes("title"), name).toBeTruthy();
		}
	});
});
