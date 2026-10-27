import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createMemoryHistory, createRouter } from "vue-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const getPage = vi.fn();
const listPages = vi.fn();
vi.mock("@/api/domains/facPage", () => ({
	facPage: { getPage: (...a) => getPage(...a), listPages: (...a) => listPages(...a) },
}));
vi.mock("@/api/_core", () => ({ baseCall: vi.fn(), getCall: vi.fn() }));

import PagePanel from "@/components/chat/pages/PagePanel.vue";
import { usePagePanel } from "@/composables/usePagePanel";
import { useUserStore } from "@/stores/userStore";
import PagesView from "../PagesView.vue";

const summaries = [
	{ name: "costs-a1b2c3", title: "Costs", visibility: "Only me", draft: false, modified: "2026-10-01 10:00:00" },
	{ name: "sales-d4e5f6", title: "Sales", visibility: "Shared", draft: false, modified: "2026-10-02 10:00:00" },
];
const fullPage = {
	title: "Costs",
	html: '<div class="mk-card">Costs</div>',
	script: "",
	style: "",
	draft: false,
	visibility: "Only me",
	owner_is_me: true,
};

const Blank = { template: "<div />" };
let router;
let wrapper;

async function mountAt(path) {
	await router.push(path);
	wrapper = mount(PagesView, {
		global: {
			plugins: [router],
			stubs: { NavigationSidebar: true },
		},
		props: { name: router.currentRoute.value.params.name },
		attachTo: document.body,
	});
	await flushPromises();
	return wrapper;
}

beforeEach(() => {
	setActivePinia(createPinia());
	useUserStore().user = "avery@example.com";
	router = createRouter({
		history: createMemoryHistory(),
		routes: [
			{ path: "/pages", name: "pages", component: Blank },
			{ path: "/pages/:name", name: "page", component: Blank },
			{ path: "/chat", name: "chat", component: Blank },
		],
	});
	listPages.mockReset().mockResolvedValue(summaries);
	getPage.mockReset().mockResolvedValue(fullPage);
});

afterEach(() => {
	wrapper?.unmount();
	usePagePanel().close();
});

describe("PagesView", () => {
	it("lists pages at /pages and opens one", async () => {
		const w = await mountAt("/pages");
		await w.find(".page-list-row").trigger("click");
		await flushPromises();
		expect(router.currentRoute.value.path).toBe("/pages/costs-a1b2c3");
	});

	it("says so when the list fails", async () => {
		listPages.mockRejectedValue(new Error("down"));
		const w = await mountAt("/pages");
		expect(w.text()).toContain("Your pages could not be listed.");
		expect(w.text()).not.toContain("No pages yet");
	});

	it("shows Loading… rather than an empty list until the pages arrive", async () => {
		let release;
		listPages.mockReturnValue(new Promise((resolve) => (release = resolve)));
		const w = await mountAt("/pages");
		expect(w.text()).toContain("Loading…");
		expect(w.text()).not.toContain("No pages yet");
		release(summaries);
		await flushPromises();
		expect(w.findAll(".page-list-row")).toHaveLength(2);
	});

	it("mounts the full PagePanel at /pages/:name", async () => {
		const w = await mountAt("/pages/costs-a1b2c3");
		expect(w.findComponent(PagePanel).props("name")).toBe("costs-a1b2c3");
		expect(w.find(".page-panel-pdf").exists()).toBe(true);
		expect(w.find('a[href="/app/fac-pages/costs-a1b2c3"]').exists()).toBe(true);
	});

	it("goes back to /pages on close", async () => {
		const w = await mountAt("/pages/costs-a1b2c3");
		await w.find(".page-panel-close").trigger("click");
		await flushPromises();
		expect(router.currentRoute.value.path).toBe("/pages");
	});

	it("a page that fails to load says so", async () => {
		getPage.mockRejectedValue(new Error("gone"));
		const w = await mountAt("/pages/costs-a1b2c3");
		expect(w.text()).toContain("This page could not be shown.");
	});

	it("sends share to a new chat with the request filled in", async () => {
		const w = await mountAt("/pages/costs-a1b2c3");
		w.findComponent(PagePanel).vm.$emit("share", "Share this page with my team");
		await flushPromises();
		expect(router.currentRoute.value.path).toBe("/chat");
		expect(router.currentRoute.value.query.prompt).toBe(
			"Share my page “Costs” (costs-a1b2c3) with my team",
		);
		expect(usePagePanel().openName.value).toBe("costs-a1b2c3");
	});

	it("leaves the dock closed when sharing on a phone", async () => {
		// isNarrow() reads matchMedia; a phone matches the narrow query.
		window.matchMedia = vi.fn().mockReturnValue({ matches: true });
		try {
			const w = await mountAt("/pages/costs-a1b2c3");
			w.findComponent(PagePanel).vm.$emit("share", "x");
			await flushPromises();
			expect(usePagePanel().openName.value).toBe(null);
			expect(router.currentRoute.value.path).toBe("/chat");
			expect(router.currentRoute.value.query.prompt).toContain("costs-a1b2c3");
		} finally {
			delete window.matchMedia;
		}
	});
});
