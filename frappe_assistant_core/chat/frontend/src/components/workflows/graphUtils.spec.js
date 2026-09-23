import { describe, it, expect } from "vitest";
import { NODE_TYPES, getDefaultLabel } from "./graphUtils.js";

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
