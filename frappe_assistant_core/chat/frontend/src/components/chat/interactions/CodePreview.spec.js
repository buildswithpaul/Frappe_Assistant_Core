import { flushPromises, mount } from "@vue/test-utils";
import { describe, it, expect, vi } from "vitest";
import { ensureHljs, highlightCode } from "@/utils/markdown";
import { lineDiff } from "./lineDiff";
import CodePreview from "./CodePreview.vue";

vi.mock("@/utils/markdown", async (importOriginal) => {
	const original = await importOriginal();
	return { ...original, highlightCode: vi.fn(original.highlightCode) };
});

vi.mock("./lineDiff", async (importOriginal) => {
	const original = await importOriginal();
	return { ...original, lineDiff: vi.fn(original.lineDiff) };
});

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

	it("shows the new code alone when the code is too large to diff", () => {
		const wrapper = mount(CodePreview, {
			props: { code: script(2100), previous: script(2100).replace("line_5 =", "changed ="), language: "python" },
		});
		expect(wrapper.find(".diff-line").exists()).toBe(false);
		expect(wrapper.find("pre").text()).toContain("line_2099 = 2099");
	});

	it("highlights each diff line once, not on every render", async () => {
		const wrapper = mount(CodePreview, { props: { code: "a\nnew\nc", previous: "a\nold\nc", language: "python" } });
		await new Promise((r) => setTimeout(r, 0));
		highlightCode.mockClear();
		await wrapper.find(".code-toggle").trigger("click");
		await wrapper.find(".code-toggle").trigger("click");
		expect(highlightCode).not.toHaveBeenCalled();
	});

	it("does not re-run the line diff when highlighting loads", async () => {
		await ensureHljs();
		lineDiff.mockClear();
		mount(CodePreview, { props: { code: "a\nnew", previous: "a\nold", language: "python" } });
		await flushPromises();
		expect(lineDiff).toHaveBeenCalledTimes(1);
	});
});
