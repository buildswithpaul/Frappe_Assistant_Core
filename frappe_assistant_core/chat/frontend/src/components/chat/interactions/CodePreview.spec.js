import { mount } from "@vue/test-utils";
import { describe, it, expect } from "vitest";
import CodePreview from "./CodePreview.vue";

const script = (n) => Array.from({ length: n }, (_, i) => `line_${i} = ${i}`).join("\n");

describe("CodePreview", () => {
	it("renders full code without truncation", () => {
		const wrapper = mount(CodePreview, { props: { code: script(400), language: "python" } });
		const text = wrapper.find("pre").text();
		expect(text).toContain("line_0 = 0");
		expect(text).toContain("line_399 = 399");
		expect(text).not.toContain("…");
		expect(wrapper.find(".code-scroll").attributes("style")).toContain("max-height: 320px");
	});

	it("code block expands and collapses", async () => {
		const wrapper = mount(CodePreview, { props: { code: script(50), language: "python", maxHeight: 200 } });
		const toggle = wrapper.find(".code-toggle");
		expect(toggle.text()).toBe("Expand");
		expect(wrapper.find(".code-scroll").attributes("style")).toContain("max-height: 200px");
		await toggle.trigger("click");
		expect(toggle.text()).toBe("Collapse");
		expect(wrapper.find(".code-scroll").attributes("style") || "").not.toContain("max-height");
		await toggle.trigger("click");
		expect(wrapper.find(".code-scroll").attributes("style")).toContain("max-height: 200px");
	});

	it("shows removed and added lines when given previous code", () => {
		const wrapper = mount(CodePreview, {
			props: { code: "a\nnew\nc", previous: "a\nold\nc", language: "python" },
		});
		expect(wrapper.find(".diff-del").text()).toContain("old");
		expect(wrapper.find(".diff-add").text()).toContain("new");
		expect(wrapper.findAll(".diff-same")).toHaveLength(2);
	});

	it("shows the code alone when there is no previous code", () => {
		const wrapper = mount(CodePreview, { props: { code: "a\nb", language: "python" } });
		expect(wrapper.find(".diff-add").exists()).toBe(false);
	});
});
