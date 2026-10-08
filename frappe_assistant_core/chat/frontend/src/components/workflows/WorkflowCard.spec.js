import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import WorkflowCard from "@/components/workflows/WorkflowCard.vue";

setActivePinia(createPinia());
const wf = { name: "WF-1", workflow_name: "Digest", status: "Draft" };

describe("WorkflowCard keyboard access", () => {
	it("is a focusable button", () => {
		const w = mount(WorkflowCard, { props: { workflow: wf } });
		expect(w.attributes("role")).toBe("button");
		expect(w.attributes("tabindex")).toBe("0");
	});

	it("opens on Enter and on Space", async () => {
		const w = mount(WorkflowCard, { props: { workflow: wf } });
		await w.trigger("keydown", { key: "Enter" });
		await w.trigger("keydown", { key: " " });
		expect(w.emitted("click")).toHaveLength(2);
	});
});
