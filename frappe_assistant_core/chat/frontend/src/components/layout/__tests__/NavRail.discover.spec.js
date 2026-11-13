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
import { useSuggestionStore } from "@/stores/suggestionStore";
import { useWorkflowStore } from "@/stores/workflowStore";
import { agentsCreated, noteAgentCreated } from "@/composables/agentCreated";

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
async function mountRail({ state = {}, switches = {}, discovery = POWERS, notifications = [], sessions = [], pages = [], before = () => {} } = {}) {
	const pinia = createPinia();
	setActivePinia(pinia);
	baseCall.mockReset().mockResolvedValue({});
	Object.assign(useUserStore(), {
		user: USER,
		memoryEnabled: true,
		workflowsEnabled: true,
		capabilities: discovery ? { discovery } : {},
		discoveryPrefs: { show_progress: true, ...switches, state },
	});
	Object.assign(usePagesStore(), { pages, loaded: true });
	before();
	useChatStore().hydrateSessions(sessions);
	useNotificationStore().notifications = notifications.map((n) => ({ ...n }));
	const router = createRouter({
		history: createMemoryHistory(),
		routes: ["/chat", "/chat/:sessionId", "/knowledge", "/agents", "/analytics", "/settings/home"].map((path) => ({
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

describe("NavRail bot: only the user's own work counts", () => {
	const label = (w) => bot(w).attributes("aria-label");

	it("a colleague's shared Page does not tick Pages; the user's own does", async () => {
		expect(label(await mountRail({ pages: [{ name: "team-report", owner_is_me: false }] }))).toBe("Your FAC: 1 of 6 tried");
		expect(label(await mountRail({ pages: [{ name: "my-report", owner_is_me: true }] }))).toBe("Your FAC: 2 of 6 tried");
	});

	it("the site's agents do not tick Agents; creating one does", async () => {
		agentsCreated.value = 0;
		// AR lists every agent on the site, with no word on who made it.
		const w = await mountRail({ before: () => (useWorkflowStore().workflows = [{ name: "WF-1" }]) });
		expect(label(w)).toBe("Your FAC: 1 of 6 tried");
		noteAgentCreated();
		await flushPromises();
		expect(label(w)).toBe("Your FAC: 2 of 6 tried");
		agentsCreated.value = 0;
	});

	it("a file someone else uploaded does not tick Knowledge; the user's own does", async () => {
		const w = await mountRail();
		useDiscoveryStore().reportKnowledge([{ document_id: "d1", is_owner: false }]);
		await flushPromises();
		expect(label(w)).toBe("Your FAC: 1 of 6 tried");
		useDiscoveryStore().reportKnowledge([{ document_id: "d2", is_owner: true }]);
		await flushPromises();
		expect(label(w)).toBe("Your FAC: 2 of 6 tried");
	});
});

describe("NavRail bot: Ask and Pages explain first", () => {
	async function openTry(w, id) {
		await bot(w).trigger("click");
		await flushPromises();
		await w.find(`[data-test='power-try-${id}']`).trigger("click");
		await flushPromises();
	}

	// FAC starts every chat as a session (/chat/<id>); the question waits for it, as a project's first message.
	const newChat = () =>
		baseCall.mockImplementation(async (method) =>
			method === "frappe_assistant_core.chat.api.create_session" ? { session_id: "s-new" } : {}
		);

	it("Try on Ask shows what it is, and its button opens a new chat with the user's short starter queued", async () => {
		const w = await mountRail({ discovery: POWERS });
		newChat();
		useSuggestionStore().allSuggestions = [
			{ source: "curated", description: "Analyze customer relationship data…" },
			{ source: "curated", kind: "find", description: "Which items are below reorder level?" },
		];
		await openTry(w, "ask");
		expect(w.find("[data-test='your-fac-panel']").exists()).toBe(false);
		expect(w.find("[data-test='spotlight-card'] h2").text()).toBe("Ask your data in plain words");
		await w.find("[data-test='spotlight-primary']").trigger("click");
		await flushPromises();
		expect(w.router.currentRoute.value.path).toBe("/chat/s-new");
		expect(useChatStore().takeFirstMessage("s-new")).toBe("Which items are below reorder level?");
		expect(w.find("[data-test='spotlight-card']").exists()).toBe(false);
	});

	it("Try on Pages explains Pages first; Maybe later asks nothing", async () => {
		const w = await mountRail({ discovery: POWERS });
		await openTry(w, "pages");
		expect(w.find("[data-test='spotlight-card'] h2").text()).toBe("Pages: live reports from any answer");
		await w.find("[data-test='spotlight-secondary']").trigger("click");
		await flushPromises();
		expect(w.find("[data-test='spotlight-card']").exists()).toBe(false);
		expect(w.router.currentRoute.value.path).toBe("/chat");
	});

	it("Pages' button asks for a Page in a new chat and counts Pages as opened", async () => {
		const w = await mountRail({ discovery: POWERS });
		newChat();
		await openTry(w, "pages");
		await w.find("[data-test='spotlight-primary']").trigger("click");
		await flushPromises();
		expect(w.router.currentRoute.value.path).toBe("/chat/s-new");
		expect(useChatStore().takeFirstMessage("s-new")).toBe("Show sales by customer for the last 3 months and save it as a Page.");
		expect(useDiscoveryStore().state.seen).toContain("pages");
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
