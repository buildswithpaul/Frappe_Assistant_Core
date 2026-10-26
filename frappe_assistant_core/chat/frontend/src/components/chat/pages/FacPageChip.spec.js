import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { usePagePanel } from "@/composables/usePagePanel";
import FacPageChip from "./FacPageChip.vue";

const chip = { name: "sales-a1b2c3", title: "Sales this month", version: 2, pending: false };

describe("FacPageChip beside a page dock (the SPA)", () => {
	let unregister;
	beforeEach(() => (unregister = usePagePanel().registerDock()));
	afterEach(() => {
		unregister();
		usePagePanel().close();
	});

	it("shows the title and version", () => {
		const text = mount(FacPageChip, { props: { chip } }).text();
		expect(text).toContain("Sales this month");
		expect(text).toContain("v2");
	});

	it("opens the page in the panel when clicked", async () => {
		await mount(FacPageChip, { props: { chip } }).find("button").trigger("click");
		expect(usePagePanel().openName.value).toBe("sales-a1b2c3");
	});
});

describe("FacPageChip without a page dock (the Desk widget)", () => {
	it("links to the page in Desk instead of opening a panel that is not there", () => {
		const w = mount(FacPageChip, { props: { chip } });
		expect(w.find("button").exists()).toBe(false);
		const link = w.find("a.fac-page-chip");
		expect(link.attributes("href")).toBe("/app/fac-pages/sales-a1b2c3");
		expect(link.text()).toContain("Sales this month");
	});
});
