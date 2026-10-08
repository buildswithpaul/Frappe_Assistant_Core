import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("@vue-flow/core", () => ({
	Handle: { name: "Handle", render: () => null },
	Position: { Left: "left", Right: "right", Top: "top", Bottom: "bottom" },
}));

import ToolNode from "./ToolNode.vue";
import LoopNode from "./LoopNode.vue";
import AgentNode from "./AgentNode.vue";
import ConditionNode from "./ConditionNode.vue";
import TransformNode from "./TransformNode.vue";
import InputNode from "./InputNode.vue";
import OutputNode from "./OutputNode.vue";

describe("ToolNode", () => {
	it("shows the chosen tool and server", () => {
		const w = mount(ToolNode, {
			props: {
				data: {
					label: "Fetch AR",
					config: { tool_name: "generate_report", server: "Main Frappe Site" },
				},
			},
		});
		expect(w.text()).toContain("Fetch AR");
		expect(w.text()).toContain("generate_report");
		expect(w.text()).toContain("Main Frappe Site");
	});

	it("says when no tool is chosen yet", () => {
		const w = mount(ToolNode, { props: { data: { label: "Tool", config: { tool_name: "" } } } });
		expect(w.text()).toContain("No tool chosen");
	});
});

describe("LoopNode", () => {
	it("shows what it iterates and the item cap", () => {
		const w = mount(LoopNode, {
			props: { data: { label: "Per customer", config: { items_path: "rows", max_items: 50 } } },
		});
		expect(w.text()).toContain("rows");
		expect(w.text()).toContain("50");
	});
});

describe("issue marker", () => {
	it("marks a node that has validation issues", () => {
		const w = mount(AgentNode, {
			props: {
				data: { label: "Draft", config: {}, issues: ['Task "Draft" is missing a system prompt'] },
			},
		});
		const marker = w.get('[data-test="node-issue"]');
		expect(marker.attributes("title")).toContain("missing a system prompt");
	});

	it("renders no marker on a clean node", () => {
		const w = mount(ToolNode, { props: { data: { label: "T", config: { tool_name: "x" } } } });
		expect(w.find('[data-test="node-issue"]').exists()).toBe(false);
	});

	it.each([
		["ToolNode", ToolNode],
		["LoopNode", LoopNode],
		["AgentNode", AgentNode],
		["ConditionNode", ConditionNode],
		["TransformNode", TransformNode],
		["InputNode", InputNode],
		["OutputNode", OutputNode],
	])("%s renders the marker and the invalid state", (_name, comp) => {
		const w = mount(comp, { props: { data: { label: "X", config: {}, issues: ["bad"] } } });
		expect(w.get('[data-test="node-issue"]').attributes("aria-label")).toBe("bad");
		expect(w.classes()).toContain("invalid");
	});
});
