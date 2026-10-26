import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import BrowserToolConfirm from "./BrowserToolConfirm.vue";

describe("BrowserToolConfirm", () => {
	it("tells the user what the tool does, from the shared copy", () => {
		const w = mount(BrowserToolConfirm, { props: { request: { tool_name: "take_screenshot" } } });
		expect(w.text()).toContain("capture what you're looking at");
	});

	it("uses the copy a host brings for a narrower tool", () => {
		const copy = { action: "Look at the page", detail: "FACO wants to look at the page open beside the chat." };
		const w = mount(BrowserToolConfirm, { props: { request: { tool_name: "take_screenshot", copy } } });
		expect(w.text()).toContain("Look at the page");
		expect(w.text()).toContain("page open beside the chat");
		expect(w.text()).not.toContain("what you're looking at");
	});
});
