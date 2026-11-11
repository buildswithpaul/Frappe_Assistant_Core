import { describe, it, expect, beforeAll, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createRouter, createMemoryHistory } from "vue-router";
import NavRail from "@/components/layout/NavRail.vue";
import { usePagesStore } from "@/stores/pagesStore";
import { useUserStore } from "@/stores/userStore";
import { useChatStore } from "@/stores/chatStore";
import { useDiscoveryStore } from "@/stores/discoveryStore";
import { useNotificationStore } from "@/stores/notificationStore";

const { baseCall } = vi.hoisted(() => ({ baseCall: vi.fn().mockResolvedValue({}) }));
vi.mock("@/api/domains/facPage", () => ({
	facPage: { listPages: vi.fn().mockResolvedValue([]), getPage: vi.fn() },
}));
vi.mock("@/api/_core", () => ({ baseCall, getCall: vi.fn().mockResolvedValue({}) }));

beforeAll(() => {
	window.__ = (s, args) => (args ? s.replace(/\{(\d+)\}/g, (_, i) => args[i]) : s);
});

const USER = "jane@example.com";
const POWERS = {
	progress_enabled: true,
	powers: [
		{ id: "setup", label: "Set up FAC" },
		{ id: "ask", label: "Ask your data" },
		{ id: "templates", label: "Prompt templates" },
		{ id: "knowledge", label: "Knowledge" },
		{ id: "pages", label: "Pages" },
		{ id: "agents", label: "Agents", try_route: "/agents?tab=marketplace" },
	],
};
const STORY = {
	id: "story-nov",
	display_style: "story",
	title: "New in FAC",
	dismissible: true,
	slides: [
		{ title: "One", message: "First" },
		{ title: "Two", message: "Second", action_label: "Try it", action_route: "/agents" },
	],
};

async function mountRail({ state = {}, switches = {}, discovery = POWERS, notifications = [], sessions = [] } = {}) {
	const pinia = createPinia();
	setActivePinia(pinia);
	baseCall.mockClear();
	Object.assign(useUserStore(), {
		user: USER,
		memoryEnabled: true,
		workflowsEnabled: true,
		capabilities: discovery ? { discovery } : {},
		discoveryPrefs: { show_tips: true, show_whats_new: true, show_progress: true, ...switches, state },
	});
	Object.assign(usePagesStore(), { pages: [], loaded: true });
	useChatStore().hydrateSessions(sessions);
	useNotificationStore().notifications = notifications.map((n) => ({ ...n }));
	const router = createRouter({
		history: createMemoryHistory(),
		routes: ["/chat", "/knowledge", "/agents", "/analytics", "/settings/home"].map((path) => ({
			path,
			component: { template: "<div />" },
		})),
	});
	router.push("/chat");
	await router.isReady();
	useDiscoveryStore().init();
	const w = mount(NavRail, {
		global: { plugins: [pinia, router], stubs: { FacoRobot: true, UserDropdown: true, teleport: true } },
	});
	await flushPromises();
	w.router = router;
	return w;
}

const dot = (w, id) => w.find(`[data-test="rail-dot-${id}"]`);
const bot = (w) => w.find("[data-test='rail-bot']");

describe("NavRail dots on features not opened yet", () => {
	it("shows a dot on Knowledge and Agents for a user who never opened them", async () => {
		const w = await mountRail();
		expect(dot(w, "knowledge").exists()).toBe(true);
		expect(dot(w, "agents").exists()).toBe(true);
		expect(w.find('[data-test="rail-knowledge"]').attributes("aria-label")).toBe("Knowledge Base (new for you)");
	});

	it("drops the dot once the feature was opened, and remembers it on the user's preferences", async () => {
		vi.useFakeTimers();
		const w = await mountRail({ state: { seen: ["knowledge"] } });
		expect(dot(w, "knowledge").exists()).toBe(false);
		expect(dot(w, "agents").exists()).toBe(true);

		// Opening Agents (App.vue reports every route) clears its dot at once.
		useDiscoveryStore().markRoute("/agents/WF-1");
		await flushPromises();
		expect(dot(w, "agents").exists()).toBe(false);
		vi.runOnlyPendingTimers();
		const [method, args] = baseCall.mock.calls.at(-1);
		expect(method).toBe("frappe_assistant_core.chat.api.save_discovery_state");
		expect(JSON.parse(args.state).seen).toEqual(["knowledge", "agents"]);
		vi.useRealTimers();
	});

	it("shows no dot while the first-login tour is open", async () => {
		const w = await mountRail();
		useDiscoveryStore().setCoachOpen(true);
		await flushPromises();
		expect(dot(w, "knowledge").exists()).toBe(false);
	});
});

describe("NavRail bot: Your FAC ring", () => {
	it("starts at 1 of 6 (setup counts) and goes to 2 of 6 once the user has asked", async () => {
		expect(bot(await mountRail()).attributes("aria-label")).toBe("Your FAC: 1 of 6 tried");
		expect(bot(await mountRail({ sessions: [{ session_id: "s1" }] })).attributes("aria-label")).toBe(
			"Your FAC: 2 of 6 tried"
		);
	});

	it("opens the powers panel, and Try goes where AR said", async () => {
		const w = await mountRail();
		await bot(w).trigger("click");
		await flushPromises();
		const panel = w.find("[data-test='your-fac-panel']");
		expect(panel.text()).toContain("1 of 6");
		expect(w.findAll("[data-test^='power-try-']")).toHaveLength(5);
		await w.find("[data-test='power-try-agents']").trigger("click");
		await flushPromises();
		expect(w.router.currentRoute.value.fullPath).toBe("/agents?tab=marketplace");
		expect(w.find("[data-test='your-fac-panel']").exists()).toBe(false);
	});

	it("is the plain home link when AR sends no powers, or the user turned progress off", async () => {
		for (const opts of [{ discovery: null }, { switches: { show_progress: false } }]) {
			const w = await mountRail(opts);
			expect(bot(w).exists()).toBe(false);
			expect(w.find("a.rail-bot").attributes("href")).toBe("/chat");
		}
	});
});

describe("NavRail bot: What's new story", () => {
	it("a waiting story takes the bot first; watching it marks it seen here and on AR, then the ring is back", async () => {
		const w = await mountRail({ notifications: [STORY] });
		expect(bot(w).attributes("aria-label")).toBe("What's new: New in FAC");
		expect(bot(w).text()).toContain("NEW");

		await bot(w).trigger("click");
		await flushPromises();
		expect(w.find("[data-test='story-player']").text()).toContain("First");
		await w.find("[data-test='story-next']").trigger("click");
		expect(w.find("[data-test='story-player']").text()).toContain("Second");
		await w.find("[data-test='story-next']").trigger("click");
		await flushPromises();

		expect(w.find("[data-test='story-player']").exists()).toBe(false);
		expect(useDiscoveryStore().state.stories_seen).toEqual(["story-nov"]);
		expect(baseCall).toHaveBeenCalledWith(
			"frappe_assistant_core.chat.api.notifications.dismiss_notification",
			expect.objectContaining({ notification_id: "story-nov" })
		);
		expect(bot(w).attributes("aria-label")).toBe("Your FAC: 1 of 6 tried");
	});

	it("a slide's button goes where AR said and closes the story", async () => {
		const w = await mountRail({ notifications: [STORY] });
		await bot(w).trigger("click");
		await flushPromises();
		await w.find("[data-test='story-next']").trigger("click");
		await w.find("[data-test='story-action']").trigger("click");
		await flushPromises();
		expect(w.router.currentRoute.value.path).toBe("/agents");
		expect(useDiscoveryStore().state.stories_seen).toEqual(["story-nov"]);
	});

	it("no story ring when the user turned What's new off", async () => {
		const w = await mountRail({ notifications: [STORY], switches: { show_whats_new: false } });
		expect(bot(w).attributes("aria-label")).toBe("Your FAC: 1 of 6 tried");
	});
});
