import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it } from "vitest";

import { usePagePanel } from "@/composables/usePagePanel";
import FacPageChip from "./FacPageChip.vue";

afterEach(() => usePagePanel().close());

const chip = { name: "sales-a1b2c3", title: "Sales this month", version: 2, pending: false };

describe("FacPageChip", () => {
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
