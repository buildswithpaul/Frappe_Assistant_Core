import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import PromptEditor from "./PromptEditor.vue";

describe("PromptEditor expand", () => {
	it("opens a large editor that edits the same prompt", async () => {
		const w = mount(PromptEditor, {
			props: { modelValue: "Summarise the report" },
			attachTo: document.body,
		});
		await w.get('[data-test="expand-prompt"]').trigger("click");
		const big = document.body.querySelector('[data-test="expanded-prompt"]');
		expect(big.value).toBe("Summarise the report");
		big.value = "Summarise and rank";
		big.dispatchEvent(new Event("input"));
		expect(w.emitted("update:modelValue").at(-1)).toEqual(["Summarise and rank"]);
		w.unmount();
	});
});
