import { describe, expect, it, vi, beforeEach } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { useTemplateExecution } from "./useTemplateExecution";
import { useTemplateStore } from "@/stores/templateStore";
import { templatesUsed } from "@/composables/usageSignals";

describe("useTemplateExecution: Your FAC counts a used template", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		templatesUsed.value = 0;
	});

	it("fills the ask box and counts the template as used", async () => {
		vi.spyOn(useTemplateStore(), "getRenderedPrompt").mockResolvedValue({ prompt: "Analyse my CRM" });
		const t = useTemplateExecution();
		t.useTemplate({ name: "crm-analysis", arguments: [] });
		await vi.waitFor(() => expect(t.pendingPrompt.value).toBe("Analyse my CRM"));
		expect(templatesUsed.value).toBe(1);
	});

	it("does not count one that failed to render", async () => {
		vi.spyOn(useTemplateStore(), "getRenderedPrompt").mockRejectedValue(new Error("down"));
		const t = useTemplateExecution();
		await t.submitParameters({ template: { name: "crm-analysis" }, arguments: {} });
		expect(t.pendingPrompt.value).toBe("");
		expect(templatesUsed.value).toBe(0);
	});
});
