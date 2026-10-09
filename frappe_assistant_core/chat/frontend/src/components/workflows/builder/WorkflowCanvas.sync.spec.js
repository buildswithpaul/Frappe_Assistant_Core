import { describe, it, expect, afterEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { ref, h } from "vue";
import { createPinia, setActivePinia } from "pinia";
import { useVueFlow } from "@vue-flow/core";
import WorkflowCanvas from "@/components/workflows/builder/WorkflowCanvas.vue";
import { useRunNodeStatus } from "@/composables/useRunNodeStatus";
import { useGraphValidation } from "@/composables/useGraphValidation";
import { useWorkflowGraphActions } from "@/composables/useWorkflowGraphActions";

setActivePinia(createPinia());
window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
globalThis.ResizeObserver ??= class {
	observe() {}
	unobserve() {}
	disconnect() {}
};

const agent = (id, prompt) => ({
	id,
	type: "agent",
	position: { x: 0, y: 0 },
	data: { label: id, config: { system_prompt: prompt } },
});

/**
 * Mirrors WorkflowBuilder's wiring: the builder owns `nodes`, Vue Flow is bound
 * one-way and keeps its own copies, and the composables reach the canvas through
 * useVueFlow(). Production reaches this state whenever a workflow is opened and a
 * run is polled or a node is edited — no array swap happens in between.
 */
function mountBuilder({ nodeList, run = ref(null) }) {
	const nodes = ref(nodeList);
	const edges = ref([]);
	const exposed = {};
	const scheduleAutoSave = vi.fn();
	const host = {
		setup() {
			const { updateNode, updateNodeData, findEdge } = useVueFlow();
			const sync = {
				updateNode,
				updateNodeData,
				updateEdge: (id, patch) => {
					const edge = findEdge(id);
					if (edge) Object.assign(edge, patch);
				},
			};
			useRunNodeStatus(run, ref(false), { nodes, edges, sync });
			Object.assign(
				exposed,
				useGraphValidation({
					workflowStore: { validateGraph: async () => ({ valid: true }) },
					nodes,
					edges,
					toGraphJson: () => "{}",
					sync,
				}),
				useWorkflowGraphActions({
					nodes,
					edges,
					selectedNode: ref(null),
					scheduleAutoSave,
					project: (p) => p,
					sync,
				}),
			);
			return () => h(WorkflowCanvas, { nodes: nodes.value, edges: edges.value });
		},
	};
	const wrapper = mount(host, { attachTo: document.body });
	return { wrapper, nodes, run, exposed, scheduleAutoSave };
}

describe("WorkflowCanvas live node state", () => {
	let wrapper;
	afterEach(() => wrapper?.unmount());

	it("paints a failed run's ring on the rendered node without swapping the array", async () => {
		const ctx = mountBuilder({ nodeList: [agent("a1", "Summarise")] });
		wrapper = ctx.wrapper;
		await flushPromises();
		expect(wrapper.find(".vue-flow__node").exists()).toBe(true);
		expect(wrapper.find(".vue-flow__node").classes()).not.toContain("run-failed");

		ctx.run.value = { node_runs: [{ node_id: "a1", status: "Failed" }] };
		await flushPromises();

		expect(wrapper.find(".vue-flow__node").classes()).toContain("run-failed");
		expect(ctx.scheduleAutoSave).not.toHaveBeenCalled();
	});

	it("updates the rendered issue marker after an edit that clears the prompt", async () => {
		const ctx = mountBuilder({ nodeList: [agent("a1", "Summarise")] });
		wrapper = ctx.wrapper;
		await flushPromises();
		expect(wrapper.find(".agent-node").classes()).not.toContain("invalid");

		ctx.exposed.handleNodeUpdate("a1", {
			config: { system_prompt: "" },
		});
		await flushPromises();

		expect(wrapper.find(".agent-node").classes()).toContain("invalid");
	});

	it("shows an edited label on the rendered node", async () => {
		const ctx = mountBuilder({ nodeList: [agent("a1", "Summarise")] });
		wrapper = ctx.wrapper;
		await flushPromises();

		ctx.exposed.handleNodeUpdate("a1", { label: "Renamed task" });
		await flushPromises();

		expect(wrapper.find(".vue-flow__node").text()).toContain("Renamed task");
	});
});
