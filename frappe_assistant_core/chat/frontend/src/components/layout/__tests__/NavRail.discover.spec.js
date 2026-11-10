import { describe, it, expect, beforeAll, beforeEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createRouter, createMemoryHistory } from "vue-router";
import NavRail from "@/components/layout/NavRail.vue";
import { usePagesStore } from "@/stores/pagesStore";
import { useUserStore } from "@/stores/userStore";
import { useDiscoveryStore } from "@/stores/discoveryStore";
import { DISCOVERY_KEY } from "@/components/discover/featureCatalog";

vi.mock("@/api/domains/facPage", () => ({
	facPage: { listPages: vi.fn().mockResolvedValue([]), getPage: vi.fn() },
}));
vi.mock("@/api/_core", () => ({ baseCall: vi.fn(), getCall: vi.fn() }));

beforeAll(() => {
	window.__ = (s) => s;
});

const USER = "jane@example.com";

async function mountRail({ user = {}, seen = null } = {}) {
	if (seen) localStorage.setItem(DISCOVERY_KEY(USER), JSON.stringify({ seen }));
	const pinia = createPinia();
	setActivePinia(pinia);
	Object.assign(useUserStore(), { user: USER, memoryEnabled: true, workflowsEnabled: true, ...user });
	Object.assign(usePagesStore(), { pages: [], loaded: true });
	const router = createRouter({
		history: createMemoryHistory(),
		routes: ["/chat", "/knowledge", "/agents", "/analytics"].map((path) => ({ path, component: { template: "<div />" } })),
	});
	router.push("/chat");
	await router.isReady();
	const w = mount(NavRail, {
		global: { plugins: [pinia, router], stubs: { FacoRobot: true, UserDropdown: true } },
	});
	await flushPromises();
	return w;
}

const dot = (w, id) => w.find(`[data-test="rail-dot-${id}"]`);

describe("NavRail dots on features not opened yet", () => {
	beforeEach(() => localStorage.clear());

	it("shows a dot on Knowledge and Agents for a user who never opened them", async () => {
		const w = await mountRail();
		expect(dot(w, "knowledge").exists()).toBe(true);
		expect(dot(w, "agents").exists()).toBe(true);
		expect(w.find('[data-test="rail-knowledge"]').attributes("aria-label")).toBe("Knowledge Base (new for you)");
	});

	it("drops the dot once the feature was opened", async () => {
		const w = await mountRail({ seen: ["knowledge"] });
		expect(dot(w, "knowledge").exists()).toBe(false);
		expect(dot(w, "agents").exists()).toBe(true);

		// Opening Agents (App.vue reports every route) clears its dot at once.
		useDiscoveryStore().markRoute("/agents/WF-1");
		await flushPromises();
		expect(dot(w, "agents").exists()).toBe(false);
		expect(JSON.parse(localStorage.getItem(DISCOVERY_KEY(USER))).seen).toEqual(["knowledge", "agents"]);
	});

	it("shows no dot while the first-login tour is open", async () => {
		const w = await mountRail();
		useDiscoveryStore().setCoachOpen(true);
		await flushPromises();
		expect(dot(w, "knowledge").exists()).toBe(false);
	});

	it("keeps one user's progress apart from another's on the same browser", async () => {
		localStorage.setItem(DISCOVERY_KEY("other@example.com"), JSON.stringify({ seen: ["knowledge", "agents"] }));
		const w = await mountRail();
		expect(dot(w, "knowledge").exists()).toBe(true);
	});
});
