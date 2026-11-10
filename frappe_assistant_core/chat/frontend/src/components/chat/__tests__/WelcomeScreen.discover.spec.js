import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createRouter, createMemoryHistory } from "vue-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { getHome } = vi.hoisted(() => ({ getHome: vi.fn() }));
vi.mock("@/api/client", () => ({
	api: {
		home: { get: (...a) => getHome(...a), hideSignal: vi.fn() },
		workflows: { listRuns: vi.fn().mockResolvedValue({ runs: [] }), list: vi.fn().mockResolvedValue({ workflows: [] }) },
		billing: { getQuotaStatus: vi.fn().mockResolvedValue(null) },
	},
}));

import WelcomeScreen from "../WelcomeScreen.vue";
import { useChatStore } from "@/stores/chatStore";
import { useUserStore } from "@/stores/userStore";
import { useDiscoveryStore } from "@/stores/discoveryStore";
import { DISCOVERY_KEY } from "@/components/discover/featureCatalog";

const USER = "jane@example.com";
const SESSION = { session_id: "s1", preview: "Q3 revenue", last_activity: "2026-10-16 10:00:00" };
const HOME = { area: "business", items: [] };
const mounted = [];
const stored = () => JSON.parse(localStorage.getItem(DISCOVERY_KEY(USER)) || "{}");

async function mountHome({
	sessions = [SESSION],
	flags = { workflowsEnabled: true, memoryEnabled: true },
	before = () => {},
} = {}) {
	const pinia = createPinia();
	setActivePinia(pinia);
	getHome.mockReset().mockResolvedValue(HOME);
	vi.stubGlobal("requestAnimationFrame", (cb) => {
		cb();
		return 1;
	});
	Object.assign(useUserStore(), { user: USER, ...flags });
	useChatStore().hydrateSessions(sessions);
	const router = createRouter({
		history: createMemoryHistory(),
		routes: ["/chat", "/agents", "/knowledge"].map((path) => ({ path, component: { template: "<div />" } })),
	});
	router.push("/chat");
	await router.isReady();
	before();
	const w = mount(WelcomeScreen, {
		slots: { composer: '<div class="composer-stub" />' },
		// Attached: the tour finds its stops in the document, as in the app.
		attachTo: document.body,
		global: { plugins: [pinia, router], stubs: { teleport: true } },
	});
	mounted.push(w);
	await flushPromises();
	w.router = router;
	return w;
}

const card = (w, id) => w.find(`[data-test="discover-${id}"]`);

afterEach(() => mounted.splice(0).forEach((w) => w.unmount()));

describe("WelcomeScreen feature discovery", () => {
	beforeEach(() => localStorage.clear());
	afterEach(() => vi.unstubAllGlobals());

	it("keeps day one simple: no Discover row and no tip", async () => {
		const w = await mountHome({ sessions: [] });
		expect(w.find("[data-test='discover-row']").exists()).toBe(false);
		expect(w.find("[data-test='discover-tip']").exists()).toBe(false);
	});

	it("shows only the features this user can use, each marked new until tried", async () => {
		const w = await mountHome({ flags: { workflowsEnabled: false, memoryEnabled: false } });
		expect(card(w, "agents").exists()).toBe(false);
		expect(card(w, "knowledge").exists()).toBe(false);
		expect(card(w, "pages").exists()).toBe(true);
		expect(card(w, "templates").text()).toContain("New for you");
	});

	it("shows first, then asks: a card opens the pop-up and Maybe later only closes it", async () => {
		const w = await mountHome();
		expect(w.find("[data-test='spotlight-card']").exists()).toBe(false);
		await card(w, "agents").trigger("click");
		expect(w.find("[data-test='spotlight-card'] h2").text()).toBe("Agents do routine work for you");
		expect(w.findAll("[data-test='spotlight-highlight']")).toHaveLength(3);
		await w.find("[data-test='spotlight-secondary']").trigger("click");
		expect(w.find("[data-test='spotlight-card']").exists()).toBe(false);
		expect(stored().seen ?? []).toEqual([]);
	});

	it("Give it a try on Agents opens the template marketplace and clears the feature's 'new'", async () => {
		const w = await mountHome();
		await card(w, "agents").trigger("click");
		await w.find("[data-test='spotlight-primary']").trigger("click");
		await flushPromises();
		expect(w.router.currentRoute.value.fullPath).toBe("/agents?tab=marketplace");
		expect(stored().seen).toEqual(["agents"]);
		expect(card(w, "agents").text()).not.toContain("New for you");
	});

	it("Give it a try on Pages fills the composer's question but never sends it", async () => {
		const w = await mountHome();
		await card(w, "pages").trigger("click");
		await w.find("[data-test='spotlight-primary']").trigger("click");
		await flushPromises();
		expect(w.router.currentRoute.value.path).toBe("/chat");
		expect(w.router.currentRoute.value.query.prompt).toContain("save it as a Page");
	});

	it("Give it a try on Prompt templates asks ChatView for the template browser", async () => {
		const w = await mountHome();
		await card(w, "templates").trigger("click");
		await w.find("[data-test='spotlight-primary']").trigger("click");
		expect(useDiscoveryStore().templatesRequested).toBe(1);
	});

	it("after the row is hidden, one weekly tip shows instead, and a dismissed tip stays gone", async () => {
		const w = await mountHome();
		await w.find("[data-test='discover-hide']").trigger("click");
		expect(w.find("[data-test='discover-row']").exists()).toBe(false);
		expect(stored().rowHidden).toBe(true);

		const again = await mountHome();
		const tip = again.find("[data-test='discover-tip']");
		expect(tip.exists()).toBe(true);
		expect(tip.text()).toContain("Agents");
		await again.find("[data-test='discover-tip-show']").trigger("click");
		expect(again.find("[data-test='spotlight-card'] h2").text()).toBe("Agents do routine work for you");
		await again.find("[data-test='spotlight-secondary']").trigger("click");
		await again.find("[data-test='discover-tip-dismiss']").trigger("click");
		expect(again.find("[data-test='discover-tip']").exists()).toBe(false);
		expect(stored().dismissedTips).toEqual(["agents"]);

		// Same week: no other tip yet.
		const sameWeek = await mountHome();
		expect(sameWeek.find("[data-test='discover-tip']").exists()).toBe(false);
	});
});

describe("WelcomeScreen first-login tour", () => {
	beforeEach(() => {
		localStorage.clear();
		// jsdom lays nothing out; give every element a box so the tour's stops count as on screen.
		vi.spyOn(Element.prototype, "getBoundingClientRect").mockReturnValue({
			top: 10, left: 10, right: 110, bottom: 60, width: 100, height: 50,
		});
	});
	afterEach(() => vi.restoreAllMocks());

	it("runs once for a first-time user and is skippable", async () => {
		const w = await mountHome({ sessions: [] });
		expect(w.find("[data-test='coach-tour']").exists()).toBe(true);
		expect(useDiscoveryStore().coachOpen).toBe(true);
		await w.find("[data-test='coach-skip']").trigger("click");
		expect(w.find("[data-test='coach-tour']").exists()).toBe(false);
		expect(stored().coachDone).toBe(true);

		const again = await mountHome({ sessions: [] });
		expect(again.find("[data-test='coach-tour']").exists()).toBe(false);
	});

	it("walks the stops with Next and ends on Done", async () => {
		const w = await mountHome({ sessions: [] });
		// The rail is not part of WelcomeScreen, so this mount has two stops: composer and Needs you.
		expect(w.text()).toContain("1 of 2");
		await w.find("[data-test='coach-next']").trigger("click");
		expect(w.text()).toContain("2 of 2");
		expect(w.find("[data-test='coach-next']").text()).toBe("Done");
		await w.find("[data-test='coach-next']").trigger("click");
		expect(stored().coachDone).toBe(true);
	});

	it("does not start by itself for a returning user, but Show me around starts it", async () => {
		const w = await mountHome();
		expect(w.find("[data-test='coach-tour']").exists()).toBe(false);

		// Settings → Help → "Show me around" asks first, then goes to /chat.
		const asked = await mountHome({ before: () => useDiscoveryStore().requestCoach() });
		expect(asked.find("[data-test='coach-tour']").exists()).toBe(true);
	});
});
