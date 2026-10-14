import { describe, it, expect, beforeAll, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createRouter, createMemoryHistory } from "vue-router";
import NavRail from "@/components/layout/NavRail.vue";
import { useUserStore } from "@/stores/userStore";

beforeAll(() => {
	window.__ = (s) => s;
});

const Blank = { template: "<div />" };

async function mountRail({ path = "/chat", props = {}, user = {} } = {}) {
	const pinia = createPinia();
	setActivePinia(pinia);
	Object.assign(useUserStore(), { memoryEnabled: true, workflowsEnabled: true, isAdmin: true, ...user });
	const router = createRouter({
		history: createMemoryHistory(),
		routes: ["/", "/chat", "/chat/:id", "/knowledge", "/agents", "/analytics", "/settings"].map((p) => ({
			path: p,
			component: Blank,
		})),
	});
	router.push(path);
	await router.isReady();
	const wrapper = mount(NavRail, {
		props: { activeSessionId: null, panelCollapsed: false, ...props },
		global: { plugins: [pinia, router], stubs: { FacoRobot: true, UserDropdown: { template: "<div data-test='user-menu' />" } } },
	});
	await flushPromises();
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

	it("clicking Chat with the panel open does not toggle it", async () => {
		const w = await mountRail();
		await item(w, "chat").trigger("click");
		expect(w.emitted("toggle-sidebar")).toBeUndefined();
	});

	it("gives every item an aria-label and a title", async () => {
		const w = await mountRail();
		for (const name of ["chat", "knowledge", "agents", "usage", "desk"]) {
			expect(item(w, name).attributes("aria-label"), name).toBeTruthy();
			expect(item(w, name).attributes("title"), name).toBeTruthy();
		}
	});
});
