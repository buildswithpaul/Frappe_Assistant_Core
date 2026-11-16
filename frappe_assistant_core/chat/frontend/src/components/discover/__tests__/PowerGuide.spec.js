import { describe, it, expect, beforeAll } from "vitest";
import { mount } from "@vue/test-utils";
import PowerGuide from "../PowerGuide.vue";

beforeAll(() => {
	window.__ = (s) => s;
});

describe("PowerGuide", () => {
	it("renders at the top of the page, so the template list's overlay does not cover it", () => {
		const w = mount(PowerGuide, { props: { guide: { id: "templates", text: "Pick a template" } }, attachTo: document.body });
		const guide = document.querySelector("[data-test='power-guide']");
		expect(guide.parentElement).toBe(document.body);
		w.unmount();
	});
});
