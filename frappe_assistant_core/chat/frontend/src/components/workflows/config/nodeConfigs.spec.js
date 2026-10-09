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
