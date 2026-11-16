import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { nextTick } from "vue";

const updateNodeInternals = vi.fn();

vi.mock("@vue-flow/core", () => ({
	Handle: { name: "Handle", props: ["type", "position", "id"], render: () => null },
	Position: { Left: "left", Right: "right", Top: "top", Bottom: "bottom" },
	useVueFlow: () => ({ updateNodeInternals }),
}));

import ToolNode from "./ToolNode.vue";
import LoopNode from "./LoopNode.vue";
import AgentNode from "./AgentNode.vue";
import ConditionNode from "./ConditionNode.vue";
import TransformNode from "./TransformNode.vue";
import InputNode from "./InputNode.vue";
import OutputNode from "./OutputNode.vue";
import DecisionNode from "./DecisionNode.vue";
import UnknownNode from "./UnknownNode.vue";

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

describe("DecisionNode", () => {
	const mountDecision = (config, id = "decision_1") =>
		mount(DecisionNode, { props: { id, data: { label: "Route", config } } });
	const sourceHandleIds = (w) =>
		w
			.findAllComponents({ name: "Handle" })
			.filter((h) => h.props("type") === "source")
			.map((h) => h.props("id"));

	it("shows the question and one source handle per choice, keyed by its text", () => {
		const w = mountDecision({ question: "Is this a refund?", choices: ["Refund", "Replace", "Other"] });
		expect(w.text()).toContain("Is this a refund?");
		expect(sourceHandleIds(w)).toEqual(["Refund", "Replace", "Other"]);
		expect(w.findAll('[data-test="decision-choice"]').map((c) => c.text())).toEqual([
			"Refund",
			"Replace",
			"Other",
		]);
	});

	it("gives a blank choice no handle and survives a config with no choices", () => {
		expect(sourceHandleIds(mountDecision({ question: "Q", choices: ["Yes", " "] }))).toEqual(["Yes"]);
		const bare = mountDecision({});
		expect(sourceHandleIds(bare)).toEqual([]);
		expect(bare.text()).toContain("No question yet");
	});

	it("re-measures its handles when a choice is renamed", async () => {
		updateNodeInternals.mockClear();
		const w = mountDecision({ question: "Q", choices: ["Yes", "No"] });
		await w.setProps({ data: { label: "Route", config: { question: "Q", choices: ["Yes", "Maybe"] } } });
		await nextTick();
		expect(sourceHandleIds(w)).toEqual(["Yes", "Maybe"]);
		expect(updateNodeInternals).toHaveBeenCalledWith(["decision_1"]);
	});
});

describe("UnknownNode", () => {
	it("draws a step type this builder does not know with its label and type", () => {
		const w = mount(UnknownNode, {
			props: { type: "future_step", data: { label: "From a newer builder", config: {} } },
		});
		expect(w.text()).toContain("From a newer builder");
		expect(w.text()).toContain("future_step");
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
		["DecisionNode", DecisionNode],
		["UnknownNode", UnknownNode],
	])("%s renders the marker and the invalid state", (_name, comp) => {
		const w = mount(comp, { props: { data: { label: "X", config: {}, issues: ["bad"] } } });
		expect(w.get('[data-test="node-issue"]').attributes("aria-label")).toBe("bad");
		expect(w.classes()).toContain("invalid");
	});
});
