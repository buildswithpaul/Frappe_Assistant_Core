import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount, flushPromises, enableAutoUnmount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";

vi.mock("@/api/client", () => ({
	api: {
		chat: { getSessions: vi.fn().mockResolvedValue([]) },
		suggestions: { get: vi.fn() },
		home: { get: vi.fn(), hideSignal: vi.fn() },
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

let routeChanged;
let formRefreshed;
const settle = () => new Promise((resolve) => setTimeout(resolve, 80)).then(flushPromises);
function onRoute(route, form = null) {
	// Desk raises form-refresh through jQuery on the document, once the doc has loaded.
	window.jQuery = () => ({ on: (_e, fn) => (formRefreshed = fn), off: vi.fn() });
	window.frappe = {
		get_route: () => route,
		router: { on: (_e, fn) => (routeChanged = fn), off: vi.fn() },
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
		api.home.get.mockReset().mockResolvedValue({ items: SIGNALS, area: "pipeline" });
		onRoute(["Form", "Sales Invoice", "SINV-0001"], invoiceForm);
	});
	afterEach(() => {
		delete window.frappe;
		delete window.jQuery;
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

	it("an unsaved form drops the name asks and its temporary name", async () => {
		const unsaved = { doctype: "Sales Invoice", doc: { name: "new-sales-invoice-abc" }, is_new: () => true };
		onRoute(["Form", "Sales Invoice", "new-sales-invoice-abc"], unsaved);
		api.suggestions.get.mockResolvedValue({
			suggestions: [{ name: "g", description: "Check this {doctype} before I save", source: "page" }, ...PAGE_ASKS],
		});
		const w = await mountHome();
		expect(w.findAll(".pa-chip").map((c) => c.text())).toEqual(["Check this Sales Invoice before I save"]);
		expect(w.find(".pa-subject").text()).toBe("Sales Invoice");
		expect(w.text()).not.toContain("new-sales-invoice-abc");
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

	it("a first-time user on a form sees PageAsks and no starter cards", async () => {
		api.chat.getSessions.mockResolvedValue([]);
		const w = await mountHome();
		expect(w.find(".pa").exists()).toBe(true);
		expect(w.find(".frs").exists()).toBe(false);
	});

	it("opening a conversation and picking a starter are emitted", async () => {
		onRoute(["Workspaces", "Home"]);
		const w = await mountHome();
		await w.find(".cl-row").trigger("click");
		expect(w.emitted("open-session")).toEqual([["s1"]]);
		await w.find(".hs-row").trigger("click");
		expect(w.emitted("suggestion")).toEqual([["List overdue invoices"]]);
	});

	describe("Desk navigation", () => {
		const CUSTOMER_ASKS = [{ name: "c", description: "Is {name} a good {doctype} to chase?", source: "page" }];
		const customerForm = { doctype: "Customer", doc: { name: "CUST-0001" }, is_new: () => false };
		// Desk raises the router change before the target form's doc has loaded (it still shows the
		// previous record, or nothing); form-refresh follows once the doc exists.
		async function navigateToCustomer() {
			onRoute(["Form", "Customer", "CUST-0001"], invoiceForm);
			routeChanged();
			await settle();
			onRoute(["Form", "Customer", "CUST-0001"], customerForm);
			formRefreshed();
			await settle();
		}

		it("Sales Invoice to Customer reloads the asks once the customer has loaded", async () => {
			const w = await mountHome();
			api.suggestions.get.mockResolvedValue({ suggestions: CUSTOMER_ASKS });
			await navigateToCustomer();
			expect(api.suggestions.get).toHaveBeenLastCalledWith({ type: "Form", doctype: "Customer" });
			expect(w.findAll(".pa-chip").map((c) => c.text())).toEqual(["Is CUST-0001 a good Customer to chase?"]);
		});

		it("List to Form shows the form's asks, not the list's", async () => {
			onRoute(["List", "Sales Invoice"]);
			api.suggestions.get.mockResolvedValue({
				suggestions: [{ name: "l", description: "Summarise this {doctype} list", source: "page" }],
			});
			const w = await mountHome();
			expect(w.find(".pa-chip").text()).toBe("Summarise this Sales Invoice list");
			api.suggestions.get.mockResolvedValue({ suggestions: PAGE_ASKS });
			onRoute(["Form", "Sales Invoice", "SINV-0001"], invoiceForm);
			formRefreshed();
			await settle();
			expect(w.find(".pa-subject").text()).toBe("Sales Invoice SINV-0001");
			expect(w.findAll(".pa-chip")).toHaveLength(2);
		});

		it("ignores a response for a page the user has already left", async () => {
			let resolveFirst;
			api.suggestions.get.mockReset();
			api.suggestions.get.mockImplementationOnce(() => new Promise((r) => (resolveFirst = r)));
			api.suggestions.get.mockImplementation(async ({ doctype }) => ({
				suggestions: doctype === "Customer" ? CUSTOMER_ASKS : [],
			}));
			const w = mount(WidgetWelcome);
			await flushPromises();
			await navigateToCustomer();
			resolveFirst({ suggestions: PAGE_ASKS });
			await flushPromises();
			expect(w.findAll(".pa-chip").map((c) => c.text())).toEqual(["Is CUST-0001 a good Customer to chase?"]);
		});

		it("returning to the previous page after a failed fetch fetches again", async () => {
			const w = await mountHome();
			api.suggestions.get.mockRejectedValue(new Error("offline"));
			await navigateToCustomer();
			api.suggestions.get.mockResolvedValue({ suggestions: PAGE_ASKS });
			onRoute(["Form", "Sales Invoice", "SINV-0001"], invoiceForm);
			formRefreshed();
			await settle();
			expect(w.findAll(".pa-chip")).toHaveLength(2);
		});

		it("Customer to Customer keeps the doctype while the next record loads, then names it", async () => {
			const asks = [...CUSTOMER_ASKS, { name: "d", description: "Which {doctype} owes the most?", source: "page" }];
			// A fetch for any other context stays pending, as a slow server would, until form-refresh.
			api.suggestions.get.mockImplementation(({ doctype }) =>
				doctype === "Customer" ? Promise.resolve({ suggestions: asks }) : new Promise(() => {})
			);
			onRoute(["Form", "Customer", "CUST-0001"], customerForm);
			const w = await mountHome();
			api.suggestions.get.mockClear();

			// Desk reuses the Customer form page: at the router change it still holds CUST-0001.
			onRoute(["Form", "Customer", "CUST-0002"], customerForm);
			routeChanged();
			await settle();
			expect(api.suggestions.get).not.toHaveBeenCalled();
			expect(w.find(".pa-subject").text()).toBe("Customer");
			expect(w.findAll(".pa-chip").map((c) => c.text())).toEqual(["Which Customer owes the most?"]);

			onRoute(["Form", "Customer", "CUST-0002"], { ...customerForm, doc: { name: "CUST-0002" } });
			formRefreshed();
			await settle();
			expect(w.find(".pa-subject").text()).toBe("Customer CUST-0002");
			expect(w.findAll(".pa-chip").map((c) => c.text())).toEqual([
				"Is CUST-0002 a good Customer to chase?",
				"Which Customer owes the most?",
			]);
		});

		it("an unmounted home no longer hears navigation, and mounts share one Desk registration", async () => {
			const routerOn = vi.fn();
			onRoute(["Workspaces", "Home"]);
			window.frappe.router = { on: routerOn, off: vi.fn() };
			const first = mount(WidgetWelcome);
			const second = mount(WidgetWelcome);
			await flushPromises();
			expect(routerOn).toHaveBeenCalledTimes(1);
			first.unmount();
			second.unmount();
			api.suggestions.get.mockClear();
			// A different page. Vue stops an unmounted watcher, so a subscriber leaked past unmount
			// shows only as detection still reading the route; neither may happen.
			onRoute(["Form", "Customer", "CUST-0001"], customerForm);
			const getRoute = vi.spyOn(window.frappe, "get_route");
			routerOn.mock.calls[0][1]();
			await settle();
			expect(getRoute).not.toHaveBeenCalled();
			expect(api.suggestions.get).not.toHaveBeenCalled();
		});

		it("a failed fetch leaves no stale asks under the new record's name", async () => {
			const w = await mountHome();
			api.suggestions.get.mockRejectedValue(new Error("offline"));
			await navigateToCustomer();
			expect(w.find(".pa").exists()).toBe(false);
		});
	});

	it("needs_you_enabled false hides the section", async () => {
		api.home.get.mockResolvedValue({ items: [], needs_you_enabled: false, area: "pipeline" });
		const w = await mountHome();
		expect(w.find(".ny").exists()).toBe(false);
	});

	it("the hide note opens Home page settings in a new tab", async () => {
		api.home.hideSignal.mockResolvedValue({ hidden_signals: ["sig0"] });
		const open = vi.spyOn(window, "open").mockReturnValue(null);
		const w = await mountHome();
		await w.find(".ny-options").trigger("click");
		await w.find("[role=menuitem]").trigger("click");
		expect(api.home.hideSignal).toHaveBeenCalledWith("sig0");
		await w.find(".ny-note-link").trigger("click");
		expect(open).toHaveBeenCalledWith("/copilot/settings/home", "_blank", "noopener");
	});
});
