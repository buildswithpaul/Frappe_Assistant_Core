import { describe, it, expect } from "vitest";
import { NODE_TYPES, NODE_LIMITS, clampInt, getDefaultConfig, getDefaultLabel, validateGraph } from "./graphUtils.js";

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
