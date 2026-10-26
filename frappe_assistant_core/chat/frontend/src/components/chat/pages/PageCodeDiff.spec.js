import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import PageCodeDiff from "./PageCodeDiff.vue";

const lines = (count, prefix = "line") => Array.from({ length: count }, (_, i) => `${prefix} ${i + 1}`);

describe("PageCodeDiff", () => {
	it("folds a long unchanged run between changes, keeping three lines around each change", async () => {
		const before = lines(20);
		const after = [...before];
		after[1] = "changed 2";
		after[18] = "changed 19";
		const w = mount(PageCodeDiff, { props: { approved: before.join("\n"), script: after.join("\n") } });

		const fold = w.find("button.page-code-diff-fold");
		expect(fold.text()).toBe("Show 10 unchanged lines");
		expect(w.findAll(".page-code-diff-text").map((l) => l.text())).not.toContain("line 10");

		await fold.trigger("click");
		expect(w.find("button.page-code-diff-fold").exists()).toBe(false);
		expect(w.findAll(".page-code-diff-text").map((l) => l.text())).toContain("line 10");
	});

	it("shows a first look as plain code, whole and unfolded", () => {
		const w = mount(PageCodeDiff, { props: { approved: "", script: lines(30).join("\n"), first: true } });
		expect(w.find("button.page-code-diff-fold").exists()).toBe(false);
		expect(w.findAll(".page-code-review-line.is-same")).toHaveLength(30);
		expect(w.find(".page-code-diff-summary").text()).toBe("30 lines of code");
	});
});
