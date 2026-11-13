import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createRouter, createMemoryHistory } from "vue-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { getHome } = vi.hoisted(() => ({ getHome: vi.fn() }));
vi.mock("@/api/client", () => ({
	api: {
		home: { get: (...a) => getHome(...a), hideSignal: vi.fn(), saveDiscoveryState: vi.fn().mockResolvedValue({}) },
		workflows: { listRuns: vi.fn().mockResolvedValue({ runs: [] }), list: vi.fn().mockResolvedValue({ workflows: [] }) },
		billing: { getQuotaStatus: vi.fn().mockResolvedValue(null) },
	},
}));

import WelcomeScreen from "../WelcomeScreen.vue";
import { useChatStore } from "@/stores/chatStore";
import { useUserStore } from "@/stores/userStore";
import { useDiscoveryStore } from "@/stores/discoveryStore";

const USER = "jane@example.com";
const SESSION = { session_id: "s1", preview: "Q3 revenue", last_activity: "2026-10-16 10:00:00" };
const HOME = { area: "business", items: [] };
const mounted = [];

async function mountHome({
	sessions = [SESSION],
	state = {},
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
		discoveryPrefs: { show_progress: true, ...switches, state },
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

const state = () => useDiscoveryStore().state;

afterEach(() => mounted.splice(0).forEach((w) => w.unmount()));

describe("WelcomeScreen: no Did you know tip", () => {
	it("Home shows no tip, on any day", async () => {
		const w = await mountHome({ state: { first_day: "2026-11-01" } });
		expect(w.find("[data-test='discover-tip']").exists()).toBe(false);
		expect(w.find("[data-test='spotlight-card']").exists()).toBe(false);
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
