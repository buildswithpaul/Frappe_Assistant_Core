import { describe, it, expect, vi } from "vitest";
import { ref, nextTick } from "vue";
import { useGraphValidation } from "./useGraphValidation";

const agent = (id, prompt) => ({
	id,
	type: "agent",
	position: { x: 0, y: 0 },
	data: { label: id, config: { system_prompt: prompt } },
});

function setup(nodeList, serverResult = { valid: true }) {
	const nodes = ref(nodeList);
	const edges = ref([]);
	const workflowStore = { validateGraph: vi.fn().mockResolvedValue(serverResult) };
	const v = useGraphValidation({ workflowStore, nodes, edges, toGraphJson: () => "{}" });
	return { v, nodes, edges, workflowStore };
}

describe("useGraphValidation live state", () => {
	it("blocks Run and marks the node while a prompt is missing", async () => {
		const { v, nodes } = setup([agent("draft", "")]);
		await nextTick();
		expect(v.canRun.value).toBe(false);
		expect(v.runBlockReason.value).toContain("draft");
		expect(nodes.value[0].data.issues).toHaveLength(1);

		nodes.value[0].data = { ...nodes.value[0].data, config: { system_prompt: "Summarise" } };
		await nextTick();
		expect(v.canRun.value).toBe(true);
		expect(nodes.value[0].data.issues).toEqual([]);
	});

	it("marks a node invalid on an edit, without any save", async () => {
		const { nodes } = setup([agent("draft", "Summarise")]);
		await nextTick();
		expect(nodes.value[0].data.issues ?? []).toEqual([]);
		const before = nodes.value[0].data;

		nodes.value[0].data = { ...nodes.value[0].data, config: { system_prompt: "" } };
		await nextTick();
		await nextTick();
		expect(nodes.value[0].data).not.toBe(before);
		expect(nodes.value[0].data.issues).toHaveLength(1);
	});

	it("lists live problems without waiting for a Run click", async () => {
		const { v } = setup([agent("draft", "")]);
		await nextTick();
		expect(v.visibleErrors.value).toHaveLength(1);
	});

	it("keeps Run blocked on a server rejection until a server check passes", async () => {
		const { v, workflowStore } = setup([agent("draft", "Summarise")], {
			valid: false,
			error: "Cycle detected",
		});
		await nextTick();
		expect(v.canRun.value).toBe(true);

		await v.checkOnServer();
		expect(v.canRun.value).toBe(false);
		expect(v.runBlockReason.value).toBe("Cycle detected");
		expect(v.visibleErrors.value).toContain("Cycle detected");

		workflowStore.validateGraph.mockResolvedValue({ valid: true });
		await v.checkOnServer();
		expect(v.canRun.value).toBe(true);
		expect(v.visibleErrors.value).toEqual([]);
	});
});
