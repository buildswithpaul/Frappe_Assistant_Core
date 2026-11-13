import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createRouter, createMemoryHistory } from "vue-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { getHome, dismissNotification } = vi.hoisted(() => ({ getHome: vi.fn(), dismissNotification: vi.fn() }));
// Tips ship with FAC (dailyTips.js); none of them comes from AR, so nothing here is dismissed on AR.
vi.mock("@/api/client", () => ({
	api: {
		home: { get: (...a) => getHome(...a), hideSignal: vi.fn(), saveDiscoveryState: vi.fn().mockResolvedValue({}) },
		notifications: { dismiss: (...a) => dismissNotification(...a) },
		workflows: { listRuns: vi.fn().mockResolvedValue({ runs: [] }), list: vi.fn().mockResolvedValue({ workflows: [] }) },
		billing: { getQuotaStatus: vi.fn().mockResolvedValue(null) },
	},
}));

import WelcomeScreen from "../WelcomeScreen.vue";
import { useChatStore } from "@/stores/chatStore";
import { useUserStore } from "@/stores/userStore";
import { useDiscoveryStore } from "@/stores/discoveryStore";
import { useNotificationStore } from "@/stores/notificationStore";

const USER = "jane@example.com";
const SESSION = { session_id: "s1", preview: "Q3 revenue", last_activity: "2026-10-16 10:00:00" };
const HOME = { area: "business", items: [] };
// A user FAC has known since before today; tips never show on the first day.
const KNOWN = { first_day: "2026-11-01" };
const TODAY = new Date(2026, 10, 12, 9, 0, 0);
const TOMORROW = new Date(2026, 10, 13, 9, 0, 0);

// FAC's own tips take turns in this order: ask, agents, templates, knowledge, pages. A user with a
// chat has used Ask, so their first tip is the agents one.
const AGENTS = "An agent can email you overdue invoices every Monday";
const TEMPLATES = "Save it as a prompt template";
const KNOWLEDGE = "Upload a price list";

const mounted = [];

async function mountHome({
	sessions = [SESSION],
	state = KNOWN,
	switches = {},
	before = () => {},
} = {}) {
	const pinia = createPinia();
	setActivePinia(pinia);
	getHome.mockReset().mockResolvedValue(HOME);
	vi.stubGlobal("requestAnimationFrame", (cb) => {
		cb();
		return 1;
	});
	Object.assign(useUserStore(), {
		user: USER,
		workflowsEnabled: true,
		memoryEnabled: true,
		discoveryPrefs: { show_tips: true, show_whats_new: true, show_progress: true, ...switches, state },
	});
	useChatStore().hydrateSessions(sessions);
	const router = createRouter({
		history: createMemoryHistory(),
		routes: ["/chat", "/agents", "/knowledge"].map((path) => ({ path, component: { template: "<div />" } })),
	});
	router.push("/chat");
	await router.isReady();
	useDiscoveryStore().init();
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

const tip = (w) => w.find("[data-test='discover-tip']");
const state = () => useDiscoveryStore().state;

afterEach(() => mounted.splice(0).forEach((w) => w.unmount()));

describe("WelcomeScreen Did you know tip", () => {
	beforeEach(() => {
		localStorage.clear();
		dismissNotification.mockReset().mockResolvedValue({});
		vi.useFakeTimers({ toFake: ["Date"] });
		vi.setSystemTime(TODAY);
	});
	afterEach(() => {
		vi.useRealTimers();
		vi.unstubAllGlobals();
	});

	it("shows FAC's own tip under the ask box", async () => {
		const w = await mountHome();
		expect(tip(w).text()).toContain(AGENTS);
		expect(state().tip).toEqual({ id: "agents-routine-work", date: "2026-11-12" });
	});

	it("keeps day one simple: no tip before the first chat, and none on FAC's first day with the user", async () => {
		expect(tip(await mountHome({ sessions: [] })).exists()).toBe(false);
		expect(tip(await mountHome({ state: {} })).exists()).toBe(false);
		expect(state().first_day).toBe("2026-11-12");
	});

	it("shows first, then asks: Show me opens the pop-up and Maybe later only closes it", async () => {
		const w = await mountHome();
		expect(w.find("[data-test='spotlight-card']").exists()).toBe(false);
		await w.find("[data-test='discover-tip-show']").trigger("click");
		expect(w.find("[data-test='spotlight-card'] h2").text()).toBe("Did you know?");
		expect(w.findAll("[data-test='spotlight-highlight']")).toHaveLength(1);
		expect(w.find("[data-test='spotlight-primary']").text()).toBe("Show me agents");
		await w.find("[data-test='spotlight-secondary']").trigger("click");
		expect(w.find("[data-test='spotlight-card']").exists()).toBe(false);
		expect(state().seen).toEqual([]);
	});

	it("the pop-up's button goes where the tip says, and the feature counts as opened", async () => {
		const w = await mountHome();
		await w.find("[data-test='discover-tip-show']").trigger("click");
		await w.find("[data-test='spotlight-primary']").trigger("click");
		await flushPromises();
		expect(w.router.currentRoute.value.fullPath).toBe("/agents?tab=marketplace");
		expect(state().seen).toEqual(["agents"]);
	});

	it("× hides it for today only", async () => {
		const w = await mountHome();
		await w.find("[data-test='discover-tip-dismiss']").trigger("click");
		expect(tip(w).exists()).toBe(false);

		const later = state();
		expect(tip(await mountHome({ state: later })).exists()).toBe(false);
		vi.setSystemTime(TOMORROW);
		expect(tip(await mountHome({ state: later })).exists()).toBe(true);
	});

	it("Don't show this tip again keeps it gone for good, on the user's own state, never on AR", async () => {
		const w = await mountHome();
		await w.find("[data-test='discover-tip-never']").trigger("click");
		expect(tip(w).exists()).toBe(false);
		expect(state().tips_dismissed).toEqual(["agents-routine-work"]);
		expect(dismissNotification).not.toHaveBeenCalled();

		vi.setSystemTime(TOMORROW);
		expect(tip(await mountHome({ state: state() })).text()).toContain(TEMPLATES);
	});

	it("skips a tip about a feature the user already uses", async () => {
		const w = await mountHome({ state: { ...KNOWN, used: ["agents", "templates"] } });
		expect(tip(w).text()).toContain(KNOWLEDGE);
	});

	it("one tip a day: the same tip all day, the next one the next day", async () => {
		await mountHome();
		const today = state();
		expect(tip(await mountHome({ state: today })).text()).toContain(AGENTS);
		vi.setSystemTime(TOMORROW);
		expect(tip(await mountHome({ state: today })).text()).toContain(TEMPLATES);
	});

	it("leaves out tips about a feature this site has switched off", async () => {
		const w = await mountHome({ before: () => Object.assign(useUserStore(), { workflowsEnabled: false }) });
		expect(tip(w).text()).toContain(TEMPLATES);
	});

	it("shows nothing when the user turned tips off in Settings → Home", async () => {
		expect(tip(await mountHome({ switches: { show_tips: false } })).exists()).toBe(false);
	});

	it("ignores anything AR sends: tips are FAC's own", async () => {
		const w = await mountHome({
			before: () => {
				useNotificationStore().notifications = [
					{ id: "ar-tip", display_style: "tip", title: "Did you know?", message: "From AR", feature: "agents" },
				];
			},
		});
		expect(tip(w).text()).not.toContain("From AR");
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
		const w = await mountHome({ sessions: [], state: {} });
		expect(w.find("[data-test='coach-tour']").exists()).toBe(true);
		expect(useDiscoveryStore().coachOpen).toBe(true);
		await w.find("[data-test='coach-skip']").trigger("click");
		expect(w.find("[data-test='coach-tour']").exists()).toBe(false);
		expect(state().coach_done).toBe(true);

		const again = await mountHome({ sessions: [], state: state() });
		expect(again.find("[data-test='coach-tour']").exists()).toBe(false);
	});

	it("walks the stops with Next and ends on Done", async () => {
		const w = await mountHome({ sessions: [], state: {} });
		// The rail is not part of WelcomeScreen, so this mount has two stops: composer and Needs you.
		expect(w.text()).toContain("1 of 2");
		await w.find("[data-test='coach-next']").trigger("click");
		expect(w.text()).toContain("2 of 2");
		expect(w.find("[data-test='coach-next']").text()).toBe("Done");
		await w.find("[data-test='coach-next']").trigger("click");
		expect(state().coach_done).toBe(true);
	});

	it("does not start by itself for a returning user, but Show me around starts it", async () => {
		const w = await mountHome();
		expect(w.find("[data-test='coach-tour']").exists()).toBe(false);

		// Settings → Help → "Show me around" asks first, then goes to /chat.
		const asked = await mountHome({ before: () => useDiscoveryStore().requestCoach() });
		expect(asked.find("[data-test='coach-tour']").exists()).toBe(true);
	});
});
