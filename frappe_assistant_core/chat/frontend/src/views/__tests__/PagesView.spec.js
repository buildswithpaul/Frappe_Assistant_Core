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
	{ name: "costs-a1b2c3", title: "Costs", visibility: "Only me", draft: false, roles: [], modified: "2026-10-01 10:00:00" },
	{ name: "sales-d4e5f6", title: "Sales", visibility: "Shared", draft: false, roles: ["Sales Manager"], modified: "2026-10-02 10:00:00" },
];
const withDraft = [
	...summaries,
	{ name: "hiring-aa11bb", title: "Hiring plan", visibility: "Shared", draft: true, roles: ["HR Manager"], modified: "2026-10-03 10:00:00" },
];
const headings = (w) => w.findAll(".pages-view-heading").map((h) => h.text());
const cardTitles = (w) => w.findAll(".page-card-title").map((t) => t.text());
const pill = (w, text) => w.findAll(".page-filter-pill").find((b) => b.text().startsWith(text));
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
		await w.find(".page-card").trigger("click");
		await flushPromises();
		expect(router.currentRoute.value.path).toBe("/pages/costs-a1b2c3");
	});

	it("groups pages into Your pages and Shared with you, drafts under shared, with counts", async () => {
		listPages.mockResolvedValue(withDraft);
		const w = await mountAt("/pages");
		expect(headings(w)).toEqual(["Your pages 1", "Shared with you 2"]);
		const sections = w.findAll(".pages-view-section");
		expect(sections[0].findAll(".page-card-title").map((t) => t.text())).toEqual(["Costs"]);
		expect(sections[1].findAll(".page-card-title").map((t) => t.text())).toEqual(["Sales", "Hiring plan"]);
	});

	it("filters by pill and hides a section left empty", async () => {
		listPages.mockResolvedValue(withDraft);
		const w = await mountAt("/pages");
		expect(w.findAll(".page-filter-pill").map((b) => b.text())).toEqual([
			"All 3",
			"Only you 1",
			"Shared 2",
			"Drafts 1",
		]);
		await pill(w, "Drafts").trigger("click");
		expect(cardTitles(w)).toEqual(["Hiring plan"]);
		expect(headings(w)).toEqual(["Shared with you 1"]);
		expect(pill(w, "Drafts").attributes("aria-pressed")).toBe("true");
		await pill(w, "Only you").trigger("click");
		expect(headings(w)).toEqual(["Your pages 1"]);
	});

	it("hides the Drafts pill when no page is a draft", async () => {
		const w = await mountAt("/pages");
		expect(pill(w, "Drafts")).toBeUndefined();
	});

	it("searches titles case-insensitively and the counts follow", async () => {
		listPages.mockResolvedValue(withDraft);
		const w = await mountAt("/pages");
		await w.find("input[type=search]").setValue("HIRING");
		expect(cardTitles(w)).toEqual(["Hiring plan"]);
		expect(w.findAll(".page-filter-pill").map((b) => b.text())).toEqual([
			"All 1",
			"Shared 1",
			"Drafts 1",
		]);
	});

	it("shows no Only you pill and no dead end for a user with only shared pages", async () => {
		listPages.mockResolvedValue([summaries[1]]);
		const w = await mountAt("/pages");
		expect(pill(w, "Only you")).toBeUndefined();
		expect(cardTitles(w)).toEqual(["Sales"]);
		expect(w.text()).not.toContain("No pages match");
	});

	it("says nothing matches and clears the search", async () => {
		const w = await mountAt("/pages");
		await w.find("input[type=search]").setValue("zzz");
		expect(w.text()).toContain("No pages match “zzz”.");
		expect(w.findAll(".page-card")).toHaveLength(0);
		await w.find(".pages-view-clear").trigger("click");
		expect(w.findAll(".page-card")).toHaveLength(2);
		expect(w.text()).not.toContain("No pages match");
	});

	it("says there are no pages and links back to chat", async () => {
		listPages.mockResolvedValue([]);
		const w = await mountAt("/pages");
		expect(w.text()).toContain("No pages yet");
		expect(w.find("input[type=search]").exists()).toBe(false);
		expect(w.find('a[href="/chat"]').exists()).toBe(true);
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
		expect(w.findAll(".page-card")).toHaveLength(2);
	});

	it("reloads the list when going back from a page to /pages", async () => {
		const w = await mountAt("/pages/costs-a1b2c3");
		listPages.mockClear();
		await w.setProps({ name: undefined });
		await flushPromises();
		expect(listPages).toHaveBeenCalledTimes(1);
	});

	it("labels the back button as going to the pages", async () => {
		const w = await mountAt("/pages/costs-a1b2c3");
		expect(w.find(".page-panel-back").attributes("aria-label")).toBe("Back to pages");
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
