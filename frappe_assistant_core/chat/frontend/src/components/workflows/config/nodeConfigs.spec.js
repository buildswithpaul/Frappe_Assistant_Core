import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { reactive, nextTick } from "vue";
import { setActivePinia, createPinia } from "pinia";

vi.mock("@/api/client", () => ({
	api: { workflows: { resolveWorkflowTools: vi.fn().mockResolvedValue({ resolved: [] }) } },
}));

// AgentConfig → ToolSection reads the user store.
setActivePinia(createPinia());

import ToolNodeConfig from "./ToolNodeConfig.vue";
import LoopNodeConfig from "./LoopNodeConfig.vue";
import NodeLimitsSection from "./NodeLimitsSection.vue";
import DecisionNodeConfig from "./DecisionNodeConfig.vue";
import { getDefaultConfig } from "../graphUtils";

const REPORT_TOOL = {
	name: "Main Frappe Site:generate_report",
	original_name: "generate_report",
	server: "Main Frappe Site",
	description: "Run a report",
	inputSchema: { properties: { report_name: {}, filters: {} }, required: ["report_name"] },
};

describe("ToolNodeConfig", () => {
	it("stores the bare tool name and its server when a tool is picked", async () => {
		const config = reactive(getDefaultConfig("tool"));
		const w = mount(ToolNodeConfig, { props: { config, allTools: [REPORT_TOOL] } });
		await w.get('[data-test="choose-tool"]').trigger("click");
		w.findComponent({ name: "ToolPicker" }).vm.$emit("select", REPORT_TOOL);
		await nextTick();
		expect(config.tool_name).toBe("generate_report");
		expect(config.server).toBe("Main Frappe Site");
		expect(w.emitted("update").at(-1)[0].config.tool_name).toBe("generate_report");
		expect(w.text()).toContain("report_name");
	});

	it("refuses broken argument JSON without emitting it", async () => {
		const config = reactive({ ...getDefaultConfig("tool"), tool_name: "generate_report" });
		const w = mount(ToolNodeConfig, { props: { config, allTools: [REPORT_TOOL] } });
		await w.get('[data-test="tool-arguments"]').setValue("{ broken");
		expect(w.text()).toContain("Not valid JSON");
		expect(config.arguments).toEqual({});
		expect(w.emitted("update")).toBeUndefined();
	});

	it("does not reformat the textarea while the user types valid compact JSON", async () => {
		const config = reactive({ ...getDefaultConfig("tool"), tool_name: "generate_report" });
		const w = mount(ToolNodeConfig, { props: { config, allTools: [REPORT_TOOL] } });
		const box = w.get('[data-test="tool-arguments"]');
		await box.setValue('{"report_name":"AR"}');
		await nextTick();
		expect(config.arguments).toEqual({ report_name: "AR" });
		expect(box.element.value).toBe('{"report_name":"AR"}');
	});

	it("clamps max rows to 2000", async () => {
		const config = reactive({ ...getDefaultConfig("tool"), tool_name: "x" });
		const w = mount(ToolNodeConfig, { props: { config, allTools: [] } });
		await w.get('[data-test="tool-max-rows"]').setValue("9000");
		await w.get('[data-test="tool-max-rows"]').trigger("change");
		expect(config.max_rows).toBe(2000);
	});

	it("does not edit anything when read-only", async () => {
		const config = reactive({ ...getDefaultConfig("tool"), tool_name: "x" });
		const w = mount(ToolNodeConfig, { props: { config, allTools: [], readonly: true } });
		expect(w.find('[data-test="choose-tool"]').exists()).toBe(false);
		await w.get('[data-test="tool-max-rows"]').setValue("5");
		await w.get('[data-test="tool-max-rows"]').trigger("change");
		expect(w.emitted("update")).toBeUndefined();
	});
});

describe("LoopNodeConfig", () => {
	it("caps concurrency at 5 and keeps the inline prompt editor", async () => {
		const config = reactive(getDefaultConfig("loop"));
		const w = mount(LoopNodeConfig, { props: { config, nodeId: "loop_1", allTools: [] } });
		await w.get('[data-test="loop-concurrency"]').setValue("8");
		await w.get('[data-test="loop-concurrency"]').trigger("change");
		expect(config.concurrency).toBe(5);
		expect(w.findComponent({ name: "PromptEditor" }).exists()).toBe(true);
		expect(w.find('[data-test="limit-timeout"]').exists()).toBe(false);
	});

	it("allows up to 500 failures before stopping", async () => {
		const config = reactive(getDefaultConfig("loop"));
		const w = mount(LoopNodeConfig, { props: { config, nodeId: "loop_1", allTools: [] } });
		await w.get('[data-test="loop-stop-after"]').setValue("900");
		await w.get('[data-test="loop-stop-after"]').trigger("change");
		expect(config.stop_after_failures).toBe(500);
	});
});

describe("NodeLimitsSection", () => {
	it("clears timeout to mean the workflow default and clamps tool calls", async () => {
		const config = reactive({ max_tool_calls: 25, timeout_seconds: 600 });
		const w = mount(NodeLimitsSection, { props: { config, showTimeout: true } });
		await w.get('[data-test="limit-tool-calls"]').setValue("500");
		await w.get('[data-test="limit-tool-calls"]').trigger("change");
		await w.get('[data-test="limit-timeout"]').setValue("");
		await w.get('[data-test="limit-timeout"]').trigger("change");
		expect(config.max_tool_calls).toBe(100);
		expect("timeout_seconds" in config).toBe(false);
	});
});

describe("DecisionNodeConfig", () => {
	const mountDecision = (config, props = {}) =>
		mount(DecisionNodeConfig, { props: { config, ...props } });
	const choiceInputs = (w) => w.findAll('[data-test="decision-choice-input"]');

	it("edits the question and emits the whole config", async () => {
		const config = reactive(getDefaultConfig("decision"));
		const w = mountDecision(config);
		await w.get('[data-test="decision-question"]').setValue("Is this a refund?");
		expect(config.question).toBe("Is this a refund?");
		expect(w.emitted("update").at(-1)[0].config).toEqual({
			question: "Is this a refund?",
			choices: ["Yes", "No"],
		});
	});

	it("inserts a variable into the question at the caret", async () => {
		const config = reactive({ ...getDefaultConfig("decision"), question: "Is  late?" });
		const w = mountDecision(config, { variables: { customer: "ACME" } });
		const box = w.get('[data-test="decision-question"]').element;
		box.setSelectionRange(3, 3);
		w.findComponent({ name: "VariableInserter" }).vm.$emit("insert", "{{customer}}");
		expect(config.question).toBe("Is {{customer}} late?");
	});

	it("adds, renames and removes choices within 2 to 10", async () => {
		const config = reactive(getDefaultConfig("decision"));
		const w = mountDecision(config);
		const remove = () => w.findAll('[data-test="decision-remove-choice"]');
		expect(remove().every((b) => b.attributes("disabled") !== undefined)).toBe(true);

		await w.get('[data-test="decision-add-choice"]').trigger("click");
		await choiceInputs(w)[2].setValue("Maybe ");
		await choiceInputs(w)[2].trigger("change");
		expect(config.choices).toEqual(["Yes", "No", "Maybe"]);

		await remove()[0].trigger("click");
		expect(config.choices).toEqual(["No", "Maybe"]);

		config.choices = Array.from({ length: 10 }, (_, i) => `c${i}`);
		await nextTick();
		expect(w.find('[data-test="decision-add-choice"]').exists()).toBe(false);
	});

	it("shows each rule's error inline", async () => {
		const config = reactive({ question: "", choices: ["Yes", "yes", "Uncertain", "x".repeat(61), " "] });
		const text = mountDecision(config).text();
		expect(text).toContain("Ask a question for the AI to answer");
		expect(text).toContain('"yes" is already a choice');
		expect(text).toContain('"uncertain" is reserved');
		expect(text).toContain("Keep a choice to 60 characters");
		expect(text).toContain("A choice cannot be empty");

		const few = mountDecision(reactive({ question: "Q", choices: ["Only"] }));
		expect(few.text()).toContain("Give between 2 and 10 choices");
	});

	it("does not edit anything when read-only", async () => {
		const config = reactive(getDefaultConfig("decision"));
		const w = mountDecision(config, { readonly: true });
		expect(w.find('[data-test="decision-add-choice"]').exists()).toBe(false);
		expect(w.find('[data-test="decision-remove-choice"]').exists()).toBe(false);
		await choiceInputs(w)[0].setValue("Changed");
		expect(config.choices).toEqual(["Yes", "No"]);
		expect(w.emitted("update")).toBeUndefined();
	});
});
