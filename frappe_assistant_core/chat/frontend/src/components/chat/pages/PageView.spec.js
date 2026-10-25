import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/_core", () => ({ baseCall: vi.fn(), getCall: vi.fn() }));

import PageView from "./PageView.vue";

let wrapper;
afterEach(() => wrapper?.unmount());

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
});
