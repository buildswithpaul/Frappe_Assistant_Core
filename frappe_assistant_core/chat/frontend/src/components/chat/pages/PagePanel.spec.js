import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const getPage = vi.fn();
const listMine = vi.fn();
vi.mock("@/api/domains/facPage", () => ({
	facPage: { getPage: (...a) => getPage(...a), listMine: (...a) => listMine(...a) },
}));
vi.mock("@/api/_core", () => ({ baseCall: vi.fn(), getCall: vi.fn() }));

import { usePagePanel } from "@/composables/usePagePanel";
import PagePanel from "./PagePanel.vue";

const page = (extra = {}) => ({
	title: "Sales this month",
	html: '<div class="mk-card">Sales</div>',
	script: "",
	style: "",
	draft: false,
	visibility: "Only me",
	owner_is_me: true,
	...extra,
});

let wrapper;
async function mountPanel(props = {}) {
	wrapper = mount(PagePanel, {
		props: { name: "sales-a1b2c3", version: 2, pending: false, canShare: false, user: "avery@example.com", ...props },
		attachTo: document.body,
	});
	await flushPromises();
	return wrapper;
}

beforeEach(() => {
	getPage.mockReset().mockResolvedValue(page());
	listMine.mockReset().mockResolvedValue([]);
});
afterEach(() => {
	wrapper?.unmount();
	usePagePanel().close();
});

describe("PagePanel", () => {
	it("fetches the page by its record name and shows the title, version and Full screen", async () => {
		const w = await mountPanel();
		expect(getPage).toHaveBeenCalledWith("sales-a1b2c3");
		expect(w.find(".page-panel-title").text()).toBe("Sales this month");
		expect(w.text()).toContain("v2");
		expect(w.find("a.page-panel-fullscreen").attributes("href")).toBe("/app/fac-pages/sales-a1b2c3");
	});

	it("offers Open in Desk when the script needs Desk features the chat can't run", async () => {
		getPage.mockResolvedValue(page({ script: "frappe.ui.form.on('Sales Invoice', {});" }));
		const w = await mountPanel();
		expect(w.text()).toContain("This page uses parts of Desk the chat can't run.");
		const link = w.find("a.page-panel-open-desk");
		expect(link.text()).toBe("Open in Desk");
		expect(link.attributes("href")).toBe("/app/fac-pages/sales-a1b2c3");
	});

	it("shows Updating… while a write to the page is pending", async () => {
		const w = await mountPanel({ pending: true });
		expect(w.text()).toContain("Updating…");
	});

	it("does not show Updating… otherwise", async () => {
		expect((await mountPanel()).text()).not.toContain("Updating…");
	});

	it("refetches when its refresh key changes", async () => {
		const w = await mountPanel();
		await w.setProps({ refreshKey: 1 });
		await flushPromises();
		expect(getPage).toHaveBeenCalledTimes(2);
	});

	it("puts the share request in the composer for a System Manager", async () => {
		const w = await mountPanel({ canShare: true });
		await w.find("button.page-panel-share").trigger("click");
		expect(w.emitted("share")).toEqual([["Share this page with my team"]]);
		expect(w.text()).not.toContain("A System Manager can share this page.");
	});

	it("tells anyone else that a System Manager can share it", async () => {
		const w = await mountPanel({ canShare: false });
		await w.find("button.page-panel-share").trigger("click");
		expect(w.emitted("share")).toBeUndefined();
		expect(w.text()).toContain("A System Manager can share this page.");
	});

	it("lists My pages from the API and opens the chosen one", async () => {
		listMine.mockResolvedValue([
			{ name: "costs-a1b2c3", title: "Costs" },
			{ name: "sales-a1b2c3", title: "Sales this month" },
		]);
		const w = await mountPanel();
		await w.find("button.page-panel-mine").trigger("click");
		await flushPromises();
		const items = w.findAll(".page-panel-mine-item");
		expect(items.map((i) => i.text())).toEqual(["Costs", "Sales this month"]);
		await items[0].trigger("click");
		expect(usePagePanel().openName.value).toBe("costs-a1b2c3");
	});

	it("closes from its close control", async () => {
		usePagePanel().open("sales-a1b2c3");
		const w = await mountPanel();
		await w.find("button.page-panel-close").trigger("click");
		expect(usePagePanel().openName.value).toBe(null);
	});

	it("says so when the page can't be shown", async () => {
		getPage.mockRejectedValue(new Error("This page does not exist."));
		expect((await mountPanel()).text()).toContain("This page could not be shown.");
	});
});
