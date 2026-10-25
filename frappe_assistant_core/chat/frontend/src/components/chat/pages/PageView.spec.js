import { flushPromises, mount } from "@vue/test-utils";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

const baseCall = vi.fn();
vi.mock("@/api/_core", () => ({ baseCall: (...a) => baseCall(...a), getCall: vi.fn() }));

import { usePagePanel } from "@/composables/usePagePanel";
import PageView from "./PageView.vue";

let wrapper;
afterEach(() => wrapper?.unmount());

// ECharts measures label text on a 2D canvas, which every browser has and jsdom lacks.
beforeAll(() => {
	vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
		font: "",
		measureText: (text) => ({ width: String(text).length * 7 }),
	});
});
afterAll(() => vi.restoreAllMocks());

const published = {
	title: "Sales",
	html: '<div class="mk-card">Sales this month</div>',
	script: "",
	style: ".mk-card { color: teal; }",
	draft: false,
};

function mountView(page) {
	wrapper = mount(PageView, { props: { page, user: "avery@example.com" }, attachTo: document.body });
	return wrapper;
}

describe("PageView", () => {
	it("renders a published page in a shadow root with the kit and the page's html and style", () => {
		const shadow = mountView(published).find(".page-view-host").element.shadowRoot;
		expect(shadow).not.toBeNull();
		const css = shadow.querySelector("style").textContent;
		expect(css).toContain("--mk-radius");
		expect(css.indexOf("--mk-radius")).toBeLessThan(css.indexOf(".mk-card { color: teal; }"));
		expect(shadow.querySelector(".fac-page-root > .mk-card").textContent).toBe("Sales this month");
	});

	it("runs a published page's script against the shadow root", () => {
		const page = { ...published, script: "root_element.querySelector('.mk-card').textContent = 'ran';" };
		const shadow = mountView(page).find(".page-view-host").element.shadowRoot;
		expect(shadow.querySelector(".mk-card").textContent).toBe("ran");
	});

	it("drops script tags from the html, as Desk does", () => {
		const page = { ...published, html: "<p>x</p><script>window.__ran = 1</script>" };
		const shadow = mountView(page).find(".page-view-host").element.shadowRoot;
		expect(shadow.querySelector("script")).toBeNull();
	});

	it("renders a draft in an empty-sandbox frame and never runs its script", () => {
		const page = { ...published, draft: true, script: "window.__draftRan = true;" };
		const frame = mountView(page).find("iframe");
		expect(frame.attributes("sandbox")).toBe("");
		expect(frame.attributes("srcdoc")).toContain("Sales this month");
		expect(frame.attributes("srcdoc")).toContain("--mk-radius");
		expect(wrapper.find(".page-view-host").exists()).toBe(false);
		expect(window.__draftRan).toBeUndefined();
	});

	it("reports the Desk feature a script needs", () => {
		const page = { ...published, script: "frappe.ui.form.on('x', {});" };
		expect(mountView(page).emitted("unsupported")).toEqual([["ui"]]);
	});

	it("treats a page that does not say it is published as a draft", () => {
		const { draft, ...unmarked } = published;
		const frame = mountView({ ...unmarked, script: "window.__unmarkedRan = true;" }).find("iframe");
		expect(frame.attributes("sandbox")).toBe("");
		expect(window.__unmarkedRan).toBeUndefined();
	});

	it("reports a data call the script made that failed", async () => {
		baseCall.mockRejectedValue(new Error("denied"));
		const page = { ...published, script: "frappe.db.insert({doctype: 'ToDo'}).catch(() => {});" };
		const w = mountView(page);
		await flushPromises();
		expect(w.emitted("error")[0][0].message).toBe("denied");
	});

	it("gives the script fac.chart, which draws an svg chart", () => {
		const page = {
			...published,
			html: '<div class="chart"></div>',
			script:
				"fac.chart(root_element.querySelector('.chart'), {xAxis: {type: 'category', data: ['A']}, yAxis: {}, series: [{type: 'bar', data: [3]}]});",
		};
		const shadow = mountView(page).find(".page-view-host").element.shadowRoot;
		expect(shadow.querySelector(".chart svg")).not.toBeNull();
		expect(wrapper.emitted("error")).toBeUndefined();
	});

	it("disposes the page's charts when it unmounts", () => {
		const page = {
			...published,
			html: '<div class="chart"></div>',
			script: "fac.chart(root_element.querySelector('.chart'), {series: [{type: 'pie', data: [1, 2]}]});",
		};
		const shadow = mountView(page).find(".page-view-host").element.shadowRoot;
		const el = shadow.querySelector(".chart");
		expect(el.querySelector("svg")).not.toBeNull();
		wrapper.unmount();
		wrapper = null;
		expect(el.querySelector("svg")).toBeNull();
	});

	it("snapshots the rendered page for print, after the script and its charts ran", () => {
		const page = {
			...published,
			html: '<div class="chart"></div>',
			script: "fac.chart(root_element.querySelector('.chart'), {series: [{type: 'pie', data: [1, 2]}]});",
		};
		const snap = mountView(page).vm.printSnapshot();
		expect(snap.html).toMatch(/^<div class="fac-page-root">/);
		expect(snap.html).toContain("<svg");
		expect(snap.html).not.toContain("--mk-radius");
		expect(snap.kitCss).toContain("--mk-radius");
		expect(snap.style).toBe(".mk-card { color: teal; }");
		expect(snap.wide).toBe(false);
		expect(snap.draft).toBe(false);
	});

	it("calls a page wider than 900px wide", () => {
		const w = mountView(published);
		const root = w.find(".page-view-host").element.shadowRoot.querySelector(".fac-page-root");
		// jsdom lays nothing out; a browser reports the page's rendered width here.
		Object.defineProperty(root, "scrollWidth", { value: 901 });
		expect(w.vm.printSnapshot().wide).toBe(true);
	});

	it("snapshots a draft from its sanitised html", () => {
		const snap = mountView({ ...published, draft: true }).vm.printSnapshot();
		expect(snap.draft).toBe(true);
		expect(snap.html).toBe('<div class="fac-page-root"><div class="mk-card">Sales this month</div></div>');
	});

	it("offers its page element to FACO's screenshot, and withdraws it on unmount", () => {
		const w = mountView(published);
		expect(usePagePanel().pageView.value).toMatchObject({
			element: w.find(".page-view-host").element,
			draft: false,
		});
		w.unmount();
		wrapper = null;
		expect(usePagePanel().pageView.value).toBe(null);
	});

	it("marks a draft's frame, which cannot be captured", () => {
		const w = mountView({ ...published, draft: true });
		expect(usePagePanel().pageView.value).toMatchObject({ element: w.find("iframe").element, draft: true });
	});
});
