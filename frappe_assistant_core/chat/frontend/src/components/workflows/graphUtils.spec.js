import { describe, it, expect } from "vitest";
import {
	NODE_TYPES,
	NODE_LIMITS,
	clampInt,
	getDefaultConfig,
	getDefaultLabel,
	graphJsonToVueFlow,
	validateGraph,
	vueFlowToGraphJson,
} from "./graphUtils.js";

describe("agent node — Task label, agent discriminator", () => {
	it("palette chip for the agent node type is labelled 'Task'", () => {
		const agentType = NODE_TYPES.find((nt) => nt.type === "agent");
		expect(agentType).toBeDefined();
		expect(agentType.label).toBe("Task");
	});

	it("agent node type discriminator stays 'agent' (wire contract)", () => {
		const agentType = NODE_TYPES.find((nt) => nt.type === "agent");
		expect(agentType.type).toBe("agent");
	});

	it("default instance label for a new agent node is 'Task'", () => {
		expect(getDefaultLabel("agent")).toBe("Task");
	});
});

const node = (id, type, config = {}, label = id) => ({ id, type, data: { label, config } });

describe("tool and loop node types", () => {
	it("offers both in the palette", () => {
		const types = NODE_TYPES.map((t) => t.type);
		expect(types).toContain("tool");
		expect(types).toContain("loop");
	});

	it("gives a tool node the Decision 5 defaults", () => {
		expect(getDefaultConfig("tool")).toEqual({
			tool_name: "",
			server: "",
			arguments: {},
			max_rows: 200,
			output: "table",
		});
		expect(getDefaultLabel("tool")).toBe("Tool");
	});

	it("gives a loop node the Decision 6 defaults with a flat inline agent", () => {
		const cfg = getDefaultConfig("loop");
		expect(cfg).toMatchObject({
			items_path: "rows",
			max_items: 50,
			concurrency: 3,
			stop_after_failures: 3,
			system_prompt: "",
			tool_directives: [],
			max_tool_calls: 25,
		});
		expect(getDefaultLabel("loop")).toBe("For each");
	});

	it("gives an agent node the tool-call cap default", () => {
		expect(getDefaultConfig("agent").max_tool_calls).toBe(25);
	});

	it("caps numbers at the engine limits", () => {
		expect(clampInt("5000", NODE_LIMITS.tool.max_rows)).toBe(2000);
		expect(clampInt(9, NODE_LIMITS.loop.concurrency)).toBe(5);
		expect(clampInt(900, NODE_LIMITS.loop.stop_after_failures)).toBe(500);
		expect(clampInt("x", NODE_LIMITS.loop.max_items)).toBe(50);
		expect(clampInt("", NODE_LIMITS.agent.timeout_seconds)).toBe(undefined);
		expect(clampInt(10, NODE_LIMITS.agent.timeout_seconds)).toBe(30);
	});
});

describe("validateGraph issues", () => {
	it("names an unreachable node by its label and points at it", () => {
		const nodes = [
			node("in", "workflow-input", {}, "Start"),
			node("a", "agent", { system_prompt: "x" }, "Summarise"),
			node("b", "agent", { system_prompt: "y" }, "Orphan step"),
		];
		const result = validateGraph(nodes, [{ source: "in", target: "a" }]);
		expect(result.valid).toBe(false);
		expect(result.issues).toContainEqual({
			nodeId: "b",
			message: '"Orphan step" is not connected to the start',
		});
		expect(result.errors.join(" ")).not.toContain("b,");
	});

	it("requires a tool on a tool node and a prompt on a loop node", () => {
		const nodes = [
			node("t", "tool", getDefaultConfig("tool"), "Fetch AR"),
			node("l", "loop", getDefaultConfig("loop"), "Per customer"),
		];
		const result = validateGraph(nodes, [{ source: "t", target: "l" }]);
		expect(result.issues.map((i) => i.nodeId)).toEqual(["t", "l"]);
		expect(result.errors[0]).toBe('Tool step "Fetch AR" has no tool selected');
		expect(result.errors[1]).toBe('"Per customer" has no instructions for each item');
	});

	it("still flags an agent with no prompt, by label", () => {
		const result = validateGraph([node("a", "agent", { system_prompt: "" }, "Draft email")], []);
		expect(result.errors).toEqual(['Task "Draft email" is missing a system prompt']);
		expect(result.issues[0].nodeId).toBe("a");
	});
});

describe("tool name must be bare", () => {
	it("flags a server-prefixed tool name and tells the user what to do", () => {
		const nodes = [node("t", "tool", { tool_name: "Main Frappe Site:generate_report" }, "Fetch AR")];
		const result = validateGraph(nodes, []);
		expect(result.issues).toEqual([
			{
				nodeId: "t",
				message: 'Tool step "Fetch AR": use the bare tool name and set the server separately',
			},
		]);
	});

	it("accepts a bare tool name", () => {
		const result = validateGraph([node("t", "tool", { tool_name: "generate_report" })], []);
		expect(result.valid).toBe(true);
	});
});

describe("decision node", () => {
	const decision = (config = {}, label = "Refund?") =>
		node("d", "decision", { ...getDefaultConfig("decision"), question: "Refund?", ...config }, label);
	const errorsFor = (config, edges = []) => validateGraph([decision(config)], edges).errors;

	it("is offered in the palette with a Yes/No default", () => {
		expect(NODE_TYPES.map((t) => t.type)).toContain("decision");
		expect(getDefaultConfig("decision")).toEqual({ question: "", choices: ["Yes", "No"] });
		expect(getDefaultLabel("decision")).toBe("Decision");
	});

	it("accepts a question with two distinct choices", () => {
		expect(errorsFor({})).toEqual([]);
	});

	it("requires a question", () => {
		expect(errorsFor({ question: "  " })).toEqual([
			'Decision "Refund?": Ask a question for the AI to answer',
		]);
	});

	it("caps the question at 2000 characters", () => {
		expect(errorsFor({ question: "x".repeat(2000) })).toEqual([]);
		expect(errorsFor({ question: "x".repeat(2001) })[0]).toContain("longer than 2000");
	});

	it("needs between 2 and 10 choices", () => {
		expect(errorsFor({ choices: ["Yes"] })[0]).toContain("between 2 and 10");
		const ten = Array.from({ length: 10 }, (_, i) => `c${i}`);
		expect(errorsFor({ choices: ten })).toEqual([]);
		expect(errorsFor({ choices: [...ten, "c10"] })[0]).toContain("between 2 and 10");
	});

	it("rejects an empty choice, even one of spaces", () => {
		expect(errorsFor({ choices: ["Yes", "  "] })[0]).toContain("cannot be empty");
	});

	it("caps a choice at 60 characters", () => {
		expect(errorsFor({ choices: ["Yes", "n".repeat(60)] })).toEqual([]);
		expect(errorsFor({ choices: ["Yes", "n".repeat(61)] })[0]).toContain("60 characters");
	});

	it("counts surrounding spaces toward the 60, as the engine stores them", () => {
		expect(errorsFor({ choices: ["Yes", ` ${"n".repeat(59)} `] })[0]).toContain("60 characters");
	});

	it("rejects a choice repeated in another case", () => {
		expect(errorsFor({ choices: ["Yes", "yes"] })[0]).toContain('"yes" is already a choice');
	});

	it("rejects a choice repeated with surrounding spaces", () => {
		expect(errorsFor({ choices: ["Yes", " Yes "] })[0]).toContain('"Yes" is already a choice');
	});

	it("rejects a choice that is not text", () => {
		expect(errorsFor({ choices: ["Yes", 5] })[0]).toContain("cannot be empty");
	});

	it("rejects a question that is not text instead of reading it as one", () => {
		expect(errorsFor({ question: 42 })).toEqual([
			'Decision "Refund?": Ask a question for the AI to answer',
		]);
		expect(errorsFor({ question: ["Refund?"] })[0]).toContain("Ask a question");
	});

	it("reserves uncertain in any case", () => {
		expect(errorsFor({ choices: ["Yes", "Uncertain"] })[0]).toContain('"uncertain" is reserved');
	});

	it("accepts edges labelled with its choices", () => {
		const nodes = [decision(), node("a", "output"), node("b", "output")];
		const edges = [
			{ source: "d", target: "a", sourceHandle: "Yes" },
			{ source: "d", target: "b", sourceHandle: "No" },
		];
		expect(validateGraph(nodes, edges).valid).toBe(true);
	});

	it("flags an edge left behind by a renamed choice on the decision node", () => {
		const nodes = [decision({ choices: ["Approve", "No"] }), node("a", "output")];
		const result = validateGraph(nodes, [{ source: "d", target: "a", sourceHandle: "Yes" }]);
		expect(result.issues).toEqual([
			{
				nodeId: "d",
				message: 'Decision "Refund?": a connection leaves from "Yes", which is no longer a choice',
			},
		]);
	});

	it("matches an edge to a choice trimmed and ignoring case, as the engine does", () => {
		const nodes = [decision({ choices: ["complaint", " question "] }), node("a", "output"), node("b", "output")];
		const edges = [
			{ source: "d", target: "a", sourceHandle: "Complaint" },
			{ source: "d", target: "b", sourceHandle: "  QUESTION" },
		];
		expect(validateGraph(nodes, edges).valid).toBe(true);
	});

	it("still flags a label that is no choice in any case or spacing", () => {
		const nodes = [decision({ choices: ["complaint", "question"] }), node("a", "output")];
		const result = validateGraph(nodes, [{ source: "d", target: "a", sourceHandle: " Refund " }]);
		expect(result.errors).toEqual([
			'Decision "Refund?": a connection leaves from "Refund", which is no longer a choice',
		]);
	});

	it("treats a label of only spaces as unlabelled", () => {
		const nodes = [decision(), node("a", "output"), node("b", "output")];
		const result = validateGraph(nodes, [
			{ source: "d", target: "a", sourceHandle: "  " },
			{ source: "d", target: "b", sourceHandle: "No" },
		]);
		expect(result.errors).toEqual(['Decision "Refund?": connect each step from one of the choices']);
	});

	it("allows an unlabelled edge only as the sole way out", () => {
		const nodes = [decision(), node("a", "output"), node("b", "output")];
		expect(validateGraph(nodes, [{ source: "d", target: "a" }]).valid).toBe(true);
		const result = validateGraph(nodes, [
			{ source: "d", target: "a" },
			{ source: "d", target: "b", sourceHandle: "No" },
		]);
		expect(result.errors).toEqual(['Decision "Refund?": connect each step from one of the choices']);
	});
});

describe("decision edges through the graph conversion", () => {
	it("keeps each choice as the edge condition and the source handle", () => {
		const graph = {
			nodes: [
				{ id: "d", type: "decision", config: { question: "Q?", choices: ["Refund", "Replace"] } },
				{ id: "a", type: "output" },
				{ id: "b", type: "output" },
			],
			edges: [
				{ id: "e1", source: "d", target: "a", condition: "Refund" },
				{ id: "e2", source: "d", target: "b", condition: "Replace" },
			],
		};
		const { nodes, edges } = graphJsonToVueFlow(graph);
		expect(nodes[0].type).toBe("decision");
		expect(edges.map((e) => e.sourceHandle)).toEqual(["Refund", "Replace"]);

		const back = JSON.parse(vueFlowToGraphJson(nodes, edges));
		expect(back.nodes[0]).toMatchObject({ type: "decision", config: graph.nodes[0].config });
		expect(back.edges.map((e) => e.condition)).toEqual(["Refund", "Replace"]);
	});

	it("binds an edge whose label differs in case or spacing to its choice, and saves the choice", () => {
		const graph = {
			nodes: [
				{ id: "d", type: "decision", config: { question: "Q?", choices: ["complaint", " question "] } },
				{ id: "a", type: "output" },
				{ id: "b", type: "output" },
			],
			edges: [
				{ id: "e1", source: "d", target: "a", condition: "Complaint" },
				{ id: "e2", source: "d", target: "b", condition: "QUESTION " },
			],
		};
		const { nodes, edges } = graphJsonToVueFlow(graph);
		// The handle ids DecisionNode renders: the trimmed choice text.
		expect(edges.map((e) => e.sourceHandle)).toEqual(["complaint", "question"]);
		expect(validateGraph(nodes, edges).valid).toBe(true);

		const back = JSON.parse(vueFlowToGraphJson(nodes, edges));
		expect(back.edges.map((e) => e.condition)).toEqual(["complaint", "question"]);
		expect(back.nodes[0].config.choices).toEqual(["complaint", " question "]);
	});

	it("keeps an unknown decision label as is, so validation can flag it", () => {
		const graph = {
			nodes: [
				{ id: "d", type: "decision", config: { question: "Q?", choices: ["Yes", "No"] } },
				{ id: "a", type: "output" },
			],
			edges: [{ id: "e1", source: "d", target: "a", condition: "Maybe" }],
		};
		const { nodes, edges } = graphJsonToVueFlow(graph);
		expect(edges[0].sourceHandle).toBe("Maybe");
		expect(validateGraph(nodes, edges).valid).toBe(false);
		expect(JSON.parse(vueFlowToGraphJson(nodes, edges)).edges[0].condition).toBe("Maybe");
	});

	it("leaves condition-node labels untouched", () => {
		const graph = {
			nodes: [{ id: "c", type: "condition" }, { id: "a", type: "output" }],
			edges: [{ id: "e1", source: "c", target: "a", condition: "pass" }],
		};
		const { nodes, edges } = graphJsonToVueFlow(graph);
		expect(edges[0].label).toBe("pass");
		expect(JSON.parse(vueFlowToGraphJson(nodes, edges)).edges[0].condition).toBe("pass");
	});

	it("draws no label on a decision edge, so edges from several choices to one step stay readable", () => {
		// The choice is written beside its handle; three edge labels at a shared
		// last stretch stacked into one unreadable pile in the browser.
		const graph = {
			nodes: [
				{ id: "d", type: "decision", config: { question: "Q?", choices: ["complaint", "question", "order"] } },
				{ id: "a", type: "output" },
			],
			edges: ["complaint", "question", "order"].map((c) => ({ id: c, source: "d", target: "a", condition: c })),
		};
		const { nodes, edges } = graphJsonToVueFlow(graph);
		expect(edges.map((e) => e.label)).toEqual(["", "", ""]);
		expect(edges.map((e) => e.sourceHandle)).toEqual(["complaint", "question", "order"]);
		expect(JSON.parse(vueFlowToGraphJson(nodes, edges)).edges.map((e) => e.condition)).toEqual([
			"complaint",
			"question",
			"order",
		]);
	});

	it("round-trips a node type this builder does not know, config untouched", () => {
		const graph = {
			nodes: [{ id: "x", type: "future_step", config: { anything: [1, 2] } }],
			edges: [],
		};
		const { nodes, edges } = graphJsonToVueFlow(graph);
		const back = JSON.parse(vueFlowToGraphJson(nodes, edges));
		expect(back.nodes[0]).toMatchObject({ type: "future_step", config: { anything: [1, 2] } });
	});
});
