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
import { fac_page_approval_key, fac_page_approve_script } from "@/utils/facPageApproval";
import PagePanel from "./PagePanel.vue";

const USER = "avery@example.com";
const NAME = "sales-a1b2c3";
// The user clicked Run new version for this script on an earlier open.
const approve = (script) => fac_page_approve_script(USER, NAME, script);
// crypto.subtle hashes off the main thread, so a load that checks an approval outlasts flushPromises.
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
	window.localStorage.clear();
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
		const script = "frappe.ui.form.on('Sales Invoice', {});";
		await approve(script);
		getPage.mockResolvedValue(page({ script }));
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
		await approve(script);
		getPage.mockResolvedValue(page({ script }));
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
		const w = await mountPanel();
		const button = w.find("button.page-panel-pdf");
		expect(button.attributes("disabled")).toBeUndefined();
		await button.trigger("click");
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

describe("PagePanel: code FACO writes runs only after the user has seen it", () => {
	const SCRIPT = "root_element.querySelector('.mk-card').textContent = 'ran v1';";
	const SCRIPT_V2 = "root_element.querySelector('.mk-card').textContent = 'ran v2';";
	const shownText = (w) => w.find(".page-view-host").element.shadowRoot.querySelector(".mk-card").textContent;

	async function refresh(w, next) {
		getPage.mockResolvedValue(next);
		await w.setProps({ refreshKey: w.props("refreshKey") + 1 });
		await flushPromises();
	}

	it("asks on first open, and draws the html without running the script", async () => {
		getPage.mockResolvedValue(page({ script: SCRIPT }));
		const w = await mountPanel();
		expect(w.find(".page-code-review").text()).toContain("This page runs code FACO wrote.");
		expect(shownText(w)).toBe("Sales");
		expect(w.find(".page-panel-held-note").exists()).toBe(true);
		expect(usePagePanel().pageView.value.codeWaiting).toBe(true);
	});

	it("runs a changed script only once Run new version is clicked, and remembers it", async () => {
		await approve(SCRIPT);
		getPage.mockResolvedValue(page({ script: SCRIPT }));
		const w = await mountPanel();
		await until(() => expect(shownText(w)).toBe("ran v1"));

		// The version the user ran stays on screen, running, while the new one waits.
		await refresh(w, page({ script: SCRIPT_V2, html: '<div class="mk-card">New</div>' }));
		await until(() => expect(w.find(".page-code-review").text()).toContain("FACO updated this page's code."));
		expect(w.find(".page-code-review").text()).toContain("You're seeing the version you last ran.");
		expect(shownText(w)).toBe("ran v1");
		expect(w.find(".page-panel-held-note").exists()).toBe(false);
		expect(usePagePanel().pageView.value.codeWaiting).toBe(true);

		await w.find("button.page-code-review-run").trigger("click");
		await until(() => expect(shownText(w)).toBe("ran v2"));
		expect(w.find(".page-code-review").exists()).toBe(false);
		expect(usePagePanel().pageView.value.codeWaiting).toBe(false);
		expect(JSON.parse(window.localStorage.getItem(fac_page_approval_key(USER, NAME))).script).toBe(SCRIPT_V2);
	});

	it("redraws an html-only change at once, running the approved script", async () => {
		await approve(SCRIPT);
		getPage.mockResolvedValue(page({ script: SCRIPT }));
		const w = await mountPanel();
		await refresh(w, page({ script: SCRIPT, html: '<div class="mk-card">New</div><p class="added">x</p>' }));
		const added = () => w.find(".page-view-host").element.shadowRoot.querySelector(".added");
		await until(() => expect(added()).not.toBeNull());
		expect(w.find(".page-code-review").exists()).toBe(false);
		expect(shownText(w)).toBe("ran v1");
	});

	it("shows a line diff of the approved script against the new one from View changes", async () => {
		await approve(SCRIPT);
		getPage.mockResolvedValue(page({ script: SCRIPT_V2 }));
		const w = await mountPanel();
		await until(() => expect(w.find(".page-code-review").exists()).toBe(true));
		expect(w.find(".page-code-review-diff").exists()).toBe(false);
		await w.find("button.page-code-review-toggle").trigger("click");
		const lines = w.findAll(".page-code-review-line");
		expect(
			lines.map((l) => [l.classes().find((c) => c.startsWith("is-")), l.find(".page-code-diff-text").text()]),
		).toEqual([
			["is-removed", SCRIPT],
			["is-added", SCRIPT_V2],
		]);
		expect(w.find(".page-code-diff-summary").text()).toBe("1 line added, 1 line removed");
	});

	it("shows the whole new script from View changes on first open", async () => {
		getPage.mockResolvedValue(page({ script: "const a = 1;\nconst b = 2;" }));
		const w = await mountPanel();
		await w.find("button.page-code-review-toggle").trigger("click");
		// A first look is the code itself, not a wall of additions.
		expect(w.findAll(".page-code-review-line.is-added")).toHaveLength(0);
		expect(w.findAll(".page-code-diff-text").map((l) => l.text())).toEqual(["const a = 1;", "const b = 2;"]);
		expect(w.find("button.page-code-review-toggle").text()).toBe("Hide code");
	});

	it("asks every time when storage throws, keeping the version the user ran on screen", async () => {
		// A private window or blocked site data makes localStorage throw on every access.
		const denied = () => {
			throw new Error("denied");
		};
		const get = vi.spyOn(Storage.prototype, "getItem").mockImplementation(denied);
		const set = vi.spyOn(Storage.prototype, "setItem").mockImplementation(denied);
		try {
			getPage.mockResolvedValue(page({ script: SCRIPT }));
			const w = await mountPanel();
			await w.find("button.page-code-review-run").trigger("click");
			await until(() => expect(shownText(w)).toBe("ran v1"));
			await refresh(w, page({ script: SCRIPT }));
			await until(() => expect(w.find(".page-code-review").text()).toContain("This page runs code FACO wrote."));
			// Nothing remembered the approval, so the banner asks again; what runs is what was run.
			expect(shownText(w)).toBe("ran v1");
		} finally {
			get.mockRestore();
			set.mockRestore();
		}
	});

	it("never holds a Shared page", async () => {
		getPage.mockResolvedValue(page({ script: SCRIPT, visibility: "Shared" }));
		const w = await mountPanel();
		expect(w.find(".page-code-review").exists()).toBe(false);
		expect(shownText(w)).toBe("ran v1");
	});

	it("holds a page whose visibility is missing or blank", async () => {
		// get_page always sends visibility; a response without it must fail closed, not run code.
		const { visibility, ...noVisibility } = page({ script: SCRIPT });
		for (const response of [noVisibility, page({ script: SCRIPT, visibility: "" })]) {
			getPage.mockResolvedValue(response);
			const w = await mountPanel();
			expect(w.find(".page-code-review").exists()).toBe(true);
			expect(shownText(w)).toBe("Sales");
			w.unmount();
		}
	});
});
