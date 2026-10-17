import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

const getHome = vi.fn();
vi.mock("@/api/client", () => ({
	api: {
		home: { get: (...a) => getHome(...a) },
		workflows: { listRuns: vi.fn().mockResolvedValue({ runs: [] }), list: vi.fn() },
	},
}));

import WelcomeScreen from "../WelcomeScreen.vue";
import { useChatStore } from "@/stores/chatStore";
import { useSuggestionStore } from "@/stores/suggestionStore";
import { useUserStore } from "@/stores/userStore";

const ITEM = {
	id: "overdue_si",
	tone: "danger",
	source: "Sales",
	count: 3,
	title: "overdue invoices",
	detail: "Oldest 14 days",
	ask: "Which invoices are overdue?",
};
const HOME = { lens_label: "Sales", area: "sales", company: "Acme Ltd", items: [ITEM] };
const SESSION = { session_id: "s1", preview: "Q3 revenue", last_activity: "2026-10-16 10:00:00" };
const TILES = ["One?", "Two?", "Three?", "Four?"].map((d) => ({
	name: d,
	description: d,
	source: "default",
}));

async function mountHome({ sessions = [SESSION], home = HOME, disabled = false } = {}) {
	setActivePinia(createPinia());
	getHome.mockReset();
	if (home instanceof Error) getHome.mockRejectedValue(home);
	else getHome.mockResolvedValue(home);
	vi.stubGlobal("requestAnimationFrame", (cb) => {
		cb();
		return 1;
	});
	useChatStore().hydrateSessions(sessions);
	useUserStore().user = "jane@example.com";
	const suggestions = useSuggestionStore();
	suggestions.suggestionsDisabled = disabled;
	suggestions.allSuggestions = TILES;
	const w = mount(WelcomeScreen, { slots: { composer: '<div class="composer-stub" />' } });
	await flushPromises();
	return w;
}

describe("WelcomeScreen home", () => {
	beforeEach(() => localStorage.clear());

	it("renders needs-you items from the endpoint", async () => {
		const w = await mountHome();
		expect(w.find(".ny").exists()).toBe(true);
		expect(w.find(".ny-title").text()).toBe("overdue invoices");
		expect(w.find(".composer-stub").exists()).toBe(true);
	});

	it("clicking an item emits suggestion with its ask", async () => {
		const w = await mountHome();
		await w.find(".ny-main").trigger("click");
		expect(w.emitted("suggestion")).toEqual([["Which invoices are overdue?"]]);
	});

	it("day one shows FirstRunStarters and the welcome header", async () => {
		const w = await mountHome({ sessions: [] });
		expect(w.text()).toContain("Welcome, Jane. I work inside your ERPNext.");
		const cards = w.findAll(".frs-card");
		expect(cards.map((c) => c.find(".frs-label").text())).toEqual(["See it", "Find it", "Do it"]);
		expect(w.find(".hs").exists()).toBe(false);
		await cards[0].trigger("click");
		expect(w.emitted("suggestion")).toEqual([["One?"]]);
	});

	it("day one with no signals shows the explanatory empty line", async () => {
		const w = await mountHome({ sessions: [], home: { ...HOME, items: [] } });
		expect(w.text()).toContain("Approvals, assignments and overdue items for you will appear here.");
	});

	it("returning user sees Continue and HomeStarters", async () => {
		const w = await mountHome();
		expect(w.find(".cl").exists()).toBe(true);
		expect(w.find(".hs-heading").text()).toBe("Ask about your sales");
		expect(w.find(".frs-card").exists()).toBe(false);
		expect(w.text()).not.toContain("What should we work through today?");
		await w.find(".hs-row").trigger("click");
		expect(w.emitted("suggestion")).toEqual([["One?"]]);
	});

	it("falls back to a generic area before the endpoint resolves", async () => {
		const w = await mountHome({ home: new Error("boom") });
		expect(w.find(".hs-heading").text()).toBe("Ask about your business");
	});

	it("suggestions disabled keeps NeedsYou", async () => {
		const w = await mountHome({ disabled: true });
		expect(w.find(".ny").exists()).toBe(true);
		expect(w.find(".hs").exists()).toBe(false);
		const day1 = await mountHome({ sessions: [], disabled: true });
		expect(day1.find(".frs-card").exists()).toBe(false);
		expect(day1.find(".ny").exists()).toBe(true);
	});

	it("company chip shows lens and company, hidden without a default company", async () => {
		const withCompany = await mountHome();
		expect(withCompany.find(".hh-chip").text()).toBe("Sales · Acme Ltd");
		const without = await mountHome({ home: { ...HOME, company: null } });
		expect(without.find(".hh-chip").exists()).toBe(false);
	});

	it("no AttentionLine is rendered", async () => {
		const w = await mountHome();
		expect(w.find(".att").exists()).toBe(false);
		expect(w.find(".welcome-att").exists()).toBe(false);
	});
});
