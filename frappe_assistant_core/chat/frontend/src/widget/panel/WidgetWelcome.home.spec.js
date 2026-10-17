import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount, flushPromises, enableAutoUnmount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";

vi.mock("@/api/client", () => ({
	api: {
		chat: { getSessions: vi.fn().mockResolvedValue([]) },
		suggestions: { get: vi.fn() },
		home: { get: vi.fn() },
		workflows: { listRuns: vi.fn().mockResolvedValue({ runs: [] }) },
	},
}));

import { api } from "@/api/client";
import WidgetWelcome from "./WidgetWelcome.vue";
import { useUserStore } from "@/stores/userStore";

enableAutoUnmount(afterEach);

const PAGE_ASKS = [
	{ name: "page_ask_1", description: "Summarise this {doctype}: {name}", source: "page" },
	{ name: "page_ask_2", description: "What changed on {doctype} {name} recently?", source: "page" },
];
const STARTER = { name: "Overdue invoices", description: "List overdue invoices", source: "contextual" };
const SIGNALS = Array.from({ length: 4 }, (_, i) => ({
	id: `sig${i}`,
	tone: "warning",
	source: "Sales",
	count: i + 1,
	title: `signal ${i}`,
	ask: `Show signal ${i}`,
}));
const AGENTS_SIGNAL = { id: "agents", tone: "danger", source: "Agents", count: 1, title: "failed run", href: "/agents" };

function onRoute(route, form = null) {
	window.frappe = {
		get_route: () => route,
		router: { on: vi.fn(), off: vi.fn() },
		views: { formview: form ? { [route[1]]: { frm: form } } : {} },
	};
}
const invoiceForm = { doctype: "Sales Invoice", doc: { name: "SINV-0001" }, is_new: () => false };

async function mountHome() {
	const w = mount(WidgetWelcome);
	await flushPromises();
	return w;
}

describe("widget home", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		// Production runs the load after first paint; run it synchronously here.
		vi.stubGlobal("requestAnimationFrame", (fn) => fn());
		api.chat.getSessions.mockReset().mockResolvedValue([
			{ session_id: "s1", preview: "First", last_activity: "2026-10-07 09:00:00" },
			{ session_id: "s2", preview: "Second", last_activity: "2026-10-05 09:00:00" },
		]);
		api.suggestions.get.mockReset().mockResolvedValue({ suggestions: [...PAGE_ASKS, STARTER] });
		api.home.get.mockReset().mockResolvedValue({ items: SIGNALS, area: "sales" });
		onRoute(["Form", "Sales Invoice", "SINV-0001"], invoiceForm);
	});
	afterEach(() => {
		delete window.frappe;
		vi.unstubAllGlobals();
		vi.restoreAllMocks();
	});

	it("on a Sales Invoice form shows PageAsks first with the invoice name", async () => {
		const w = await mountHome();
		expect(w.find(".pa").exists()).toBe(true);
		expect(w.find(".pa-subject").text()).toBe("Sales Invoice SINV-0001");
		expect(w.findAll(".pa-chip").map((c) => c.text())).toEqual([
			"Summarise this Sales Invoice: SINV-0001",
			"What changed on Sales Invoice SINV-0001 recently?",
		]);
		const sections = w.element.children;
		expect(sections[1].classList.contains("pa")).toBe(true);
		await w.findAll(".pa-chip")[0].trigger("click");
		expect(w.emitted("suggestion")).toEqual([["Summarise this Sales Invoice: SINV-0001"]]);
	});

	it("page asks are not sent the document name to the server", async () => {
		await mountHome();
		expect(api.suggestions.get).toHaveBeenCalledWith({ type: "Form", doctype: "Sales Invoice" });
	});

	it("a list page fills asks from the doctype only and drops the name asks", async () => {
		onRoute(["List", "Sales Invoice"]);
		api.suggestions.get.mockResolvedValue({
			suggestions: [{ name: "a", description: "Summarise this {doctype} list", source: "page" }, ...PAGE_ASKS],
		});
		const w = await mountHome();
		expect(w.findAll(".pa-chip").map((c) => c.text())).toEqual(["Summarise this Sales Invoice list"]);
		expect(w.find(".pa-subject").text()).toBe("Sales Invoice");
	});

	it("hides PageAsks when the operator turned suggestions off", async () => {
		api.suggestions.get.mockResolvedValue({ suggestions: PAGE_ASKS, suggestions_disabled: true });
		const w = await mountHome();
		expect(w.find(".pa").exists()).toBe(false);
	});

	it("on a form NeedsYou caps at 2 and starters are left out", async () => {
		const w = await mountHome();
		expect(w.findAll(".ny-item")).toHaveLength(2);
		expect(w.find(".hs").exists()).toBe(false);
		expect(w.findAll(".cl-row")).toHaveLength(1);
	});

	it("on desk home shows starters and caps at 3", async () => {
		onRoute(["Workspaces", "Home"]);
		const w = await mountHome();
		expect(w.find(".pa").exists()).toBe(false);
		expect(w.findAll(".ny-item")).toHaveLength(3);
		expect(w.find(".hs").exists()).toBe(true);
		expect(w.text()).toContain("List overdue invoices");
		expect(w.text()).not.toContain("{doctype}");
	});

	it("U3 navigate opens the SPA agents page in a new tab", async () => {
		onRoute(["Workspaces", "Home"]);
		api.home.get.mockResolvedValue({ items: [AGENTS_SIGNAL] });
		const open = vi.spyOn(window, "open").mockImplementation(() => null);
		const w = await mountHome();
		await w.find(".ny-main").trigger("click");
		expect(open).toHaveBeenCalledWith("/copilot/agents", "_blank", "noopener");
	});

	it("greets the user by name in a translatable headline", async () => {
		useUserStore().user = "avery.shah@northwind.example";
		const w = await mountHome();
		expect(w.find(".hh-greeting").text()).toMatch(/^Good (morning|afternoon|evening), Avery\.$/);
	});

	it("a first-time user gets the day-one welcome and starter cards", async () => {
		api.chat.getSessions.mockResolvedValue([]);
		onRoute(["Workspaces", "Home"]);
		api.suggestions.get.mockResolvedValue({
			suggestions: [{ name: "x", description: "Show sales", kind: "see", source: "default" }, ...PAGE_ASKS],
		});
		const w = await mountHome();
		expect(w.find(".hh-greeting").text()).toContain("I work inside your ERPNext");
		expect(w.findAll(".frs-card")).toHaveLength(1);
		expect(w.find(".cl-row").exists()).toBe(false);
	});

	it("hides starters when the operator turned suggestions off", async () => {
		onRoute(["Workspaces", "Home"]);
		api.suggestions.get.mockResolvedValue({ suggestions: [], suggestions_disabled: true });
		const w = await mountHome();
		expect(w.find(".hs").exists()).toBe(false);
	});
});
