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
async function mountRail({ state = {}, switches = {}, discovery = POWERS, notifications = [], sessions = [] } = {}) {
	const pinia = createPinia();
	setActivePinia(pinia);
	baseCall.mockClear();
	Object.assign(useUserStore(), {
		user: USER,
		memoryEnabled: true,
		workflowsEnabled: true,
		capabilities: discovery ? { discovery } : {},
		discoveryPrefs: { show_tips: true, show_progress: true, ...switches, state },
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
		// As in the plan: a ring with "1 of 6 powers" and the next one to try.
		expect(panel.find("[data-test='your-fac-ring'] svg").exists()).toBe(true);
		expect(panel.find("[data-test='your-fac-count']").text()).toBe("1 of 6 powers");
		expect(panel.find("[data-test='your-fac-next']").text()).toBe("Next: Ask your data");
		// One arc per power, in its own colour once used: only setup is done here.
		const segs = panel.findAll("[data-test^='your-fac-seg-']");
		expect(segs).toHaveLength(6);
		expect(segs.map((s) => s.classes("done"))).toEqual([true, false, false, false, false, false]);
		expect(panel.find("[data-test='power-ask']").attributes("style")).toContain("--power-color: var(--ql-power-2)");
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

describe("NavRail bot: no stories in this build", () => {
	it("a story AR sends never takes the bot: the Your FAC ring stays", async () => {
		const story = { id: "story-nov", display_style: "story", title: "New in FAC", slides: [{ title: "One" }] };
		const w = await mountRail({ notifications: [story] });
		expect(bot(w).attributes("aria-label")).toBe("Your FAC: 1 of 6 tried");
		expect(bot(w).text()).not.toContain("NEW");
	});
});
