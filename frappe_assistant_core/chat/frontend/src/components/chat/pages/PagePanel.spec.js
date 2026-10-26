import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const getPage = vi.fn();
const listMine = vi.fn();
vi.mock("@/api/domains/facPage", () => ({
	facPage: { getPage: (...a) => getPage(...a), listMine: (...a) => listMine(...a) },
}));
vi.mock("@/api/_core", () => ({ baseCall: vi.fn(), getCall: vi.fn() }));
const printPage = vi.fn();
vi.mock("@/utils/pagePrint", async (importOriginal) => ({
	...(await importOriginal()),
	printPage: (...a) => printPage(...a),
}));

import { usePagePanel } from "@/composables/usePagePanel";
import PagePanel from "./PagePanel.vue";
import PageView from "./PageView.vue";

const until = (assertion) => vi.waitFor(assertion);

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
	printPage.mockReset();
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
		// A Shared page's script runs in the chat itself, where the panel sees what it reached for.
		const script = "frappe.ui.form.on('Sales Invoice', {});";
		getPage.mockResolvedValue(page({ script, visibility: "Shared" }));
		const w = await mountPanel();
		await until(() => expect(w.text()).toContain("This page uses parts of Desk the chat can't run."));
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

	it("offers Open in Desk when the script throws", async () => {
		const script = "throw new Error('x');";
		getPage.mockResolvedValue(page({ script, visibility: "Shared" }));
		const w = await mountPanel();
		await until(() => expect(w.text()).toContain("Part of this page didn't load."));
		expect(w.find("a.page-panel-open-desk").attributes("href")).toBe("/app/fac-pages/sales-a1b2c3");
	});

	it("treats a response that is not a page as a failed load", async () => {
		getPage.mockResolvedValue(null);
		const w = await mountPanel();
		expect(w.text()).toContain("This page could not be shown.");
		expect(w.text()).not.toContain("Loading…");
	});

	it("hides Share… for a page that is already Shared", async () => {
		getPage.mockResolvedValue(page({ visibility: "Shared", owner_is_me: true }));
		expect((await mountPanel({ canShare: true })).find("button.page-panel-share").exists()).toBe(false);
	});

	it("hides Share… while the page loads and when it could not be loaded", async () => {
		getPage.mockReturnValue(new Promise(() => {}));
		expect((await mountPanel({ canShare: true })).find("button.page-panel-share").exists()).toBe(false);
		wrapper.unmount();
		getPage.mockRejectedValue(new Error("gone"));
		expect((await mountPanel({ canShare: true })).find("button.page-panel-share").exists()).toBe(false);
	});

	it("hides Share… for a page someone else owns", async () => {
		getPage.mockResolvedValue(page({ owner_is_me: false }));
		expect((await mountPanel({ canShare: true })).find("button.page-panel-share").exists()).toBe(false);
	});

	it("prints the rendered page under its title from Download PDF", async () => {
		getPage.mockResolvedValue(page({ visibility: "Shared" }));
		const w = await mountPanel();
		const button = w.find("button.page-panel-pdf");
		expect(button.attributes("disabled")).toBeUndefined();
		await button.trigger("click");
		await flushPromises();
		expect(printPage).toHaveBeenCalledOnce();
		const args = printPage.mock.calls[0][0];
		expect(args.title).toBe("Sales this month");
		expect(args.html).toContain("Sales");
		expect(args.kitCss).toContain("--mk-radius");
		expect(args.wide).toBe(false);
	});

	it("offers Download PDF only once the page has loaded", async () => {
		getPage.mockRejectedValue(new Error("gone"));
		const w = await mountPanel();
		expect(w.find("button.page-panel-pdf").attributes("disabled")).toBeDefined();
	});
});

describe("PagePanel: a personal page runs on its own and asks before a change", () => {
	const SCRIPT = "root_element.querySelector('.mk-card').textContent = 'ran';";

	it("draws a personal page in its sandboxed frame at once, with no step to run its code", async () => {
		getPage.mockResolvedValue(page({ script: SCRIPT }));
		const w = await mountPanel();
		const frame = w.find("iframe.fac-page-sandbox");
		expect(frame.attributes("sandbox")).toBe("allow-scripts");
		expect(frame.attributes("srcdoc")).toContain("ran");
		expect(w.text()).not.toContain("Run new version");
		expect(w.text()).not.toContain("View code");
		expect(w.find(".page-write-prompt").exists()).toBe(false);
	});

	it("redraws a new version at once when a write to the page lands", async () => {
		getPage.mockResolvedValue(page({ script: SCRIPT }));
		const w = await mountPanel();
		getPage.mockResolvedValue(page({ script: "root_element.textContent = 'v2';" }));
		await w.setProps({ refreshKey: 1 });
		await flushPromises();
		expect(w.find("iframe.fac-page-sandbox").attributes("srcdoc")).toContain("v2");
		expect(w.text()).not.toContain("Run new version");
	});

	it("asks before a change the page wants to make, and answers with the user's choice", async () => {
		const w = await mountPanel();
		const ask = w.findComponent(PageView).props("askWrite");
		const allowed = ask("This page wants to delete ToDo TD-1.");
		await flushPromises();
		expect(w.find(".page-write-prompt").text()).toContain("This page wants to delete ToDo TD-1.");
		await w.find("[data-test=page-write-allow]").trigger("click");
		expect(await allowed).toBe(true);
		expect(w.find(".page-write-prompt").exists()).toBe(false);

		const denied = ask("This page wants to create a new ToDo.");
		await flushPromises();
		await w.find("[data-test=page-write-deny]").trigger("click");
		expect(await denied).toBe(false);
	});

	it("asks one change at a time, in order", async () => {
		const w = await mountPanel();
		const ask = w.findComponent(PageView).props("askWrite");
		const first = ask("first");
		const second = ask("second");
		await flushPromises();
		expect(w.find(".page-write-prompt-message").text()).toBe("first");
		await w.find("[data-test=page-write-allow]").trigger("click");
		expect(await first).toBe(true);
		expect(w.find(".page-write-prompt-message").text()).toBe("second");
		await w.find("[data-test=page-write-deny]").trigger("click");
		expect(await second).toBe(false);
	});

	it("refuses a change the old version asked about once a new version loads", async () => {
		const w = await mountPanel();
		const pendingAsk = w.findComponent(PageView).props("askWrite")("old version's change");
		await w.setProps({ refreshKey: 1 });
		await flushPromises();
		expect(await pendingAsk).toBe(false);
		expect(w.find(".page-write-prompt").exists()).toBe(false);
	});
});
