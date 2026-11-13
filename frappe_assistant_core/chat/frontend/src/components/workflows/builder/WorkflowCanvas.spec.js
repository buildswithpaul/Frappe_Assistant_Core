import { describe, it, expect, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { ref, computed, h } from "vue";
import { createPinia, setActivePinia } from "pinia";
import WorkflowCanvas from "@/components/workflows/builder/WorkflowCanvas.vue";
import { useWorkflowGraphActions } from "@/composables/useWorkflowGraphActions";
import { graphJsonToVueFlow } from "@/components/workflows/graphUtils";
import DecisionNode from "@/components/workflows/nodes/DecisionNode.vue";
import UnknownNode from "@/components/workflows/nodes/UnknownNode.vue";

setActivePinia(createPinia());
window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
// Every browser has ResizeObserver; jsdom does not, and Vue Flow observes its pane with one.
globalThis.ResizeObserver ??= class {
	observe() {}
	unobserve() {}
	disconnect() {}
};

/**
 * The builder reaches into this component for two things that a plain
 * props-down/events-up reading would not reveal: the canvas element itself
 * (palette clicks are projected against its box) and a drop event that is still
 * mid-dispatch (the handler resolves the pane from `currentTarget`). Both break
 * silently — a lost element only degrades node placement to a hardcoded guess.
 */
describe("WorkflowCanvas", () => {
	it("exposes the canvas element the builder projects palette clicks into", () => {
		const canvasRef = ref(null);
		const canvasAreaRef = computed(() => canvasRef.value?.rootEl || null);
		const host = mount({
			setup: () => () => h(WorkflowCanvas, { ref: canvasRef, isLoading: true }),
		});
		expect(canvasAreaRef.value).toBe(host.find(".canvas-area").element);
		expect(typeof canvasAreaRef.value.getBoundingClientRect).toBe("function");
	});

	it("runs the drop handler once, while currentTarget is still the canvas", async () => {
		const nodes = ref([]);
		const { onDrop } = useWorkflowGraphActions({
			nodes,
			edges: ref([]),
			selectedNode: ref(null),
			scheduleAutoSave: vi.fn(),
			project: (p) => p,
		});

		const calls = [];
		const w = mount(WorkflowCanvas, {
			props: {
				isLoading: true,
				onDrop: (event) => {
					calls.push(event.currentTarget);
					onDrop(event);
				},
			},
		});
		const area = w.find(".canvas-area");
		const pane = document.createElement("div");
		pane.className = "vue-flow__pane";
		area.element.appendChild(pane);

		await area.trigger("drop", { dataTransfer: { getData: () => "agent" } });

		expect(calls).toEqual([area.element]);
		expect(nodes.value.map((n) => n.type)).toEqual(["agent"]);
	});

	it("draws a node type it has no component for instead of dropping it", async () => {
		// An older builder loading a graph a newer one saved: the type comes
		// straight from the stored graph JSON through graphJsonToVueFlow.
		const { nodes } = graphJsonToVueFlow({
			nodes: [{ id: "x", type: "future_step", label: "From a newer builder", config: {} }],
			edges: [],
		});
		const w = mount(WorkflowCanvas, { props: { nodes } });
		await flushPromises();
		const node = w.findComponent(UnknownNode);
		expect(node.exists()).toBe(true);
		expect(node.text()).toContain("From a newer builder");
		expect(node.text()).toContain("future_step");
	});

	it("draws a decision node with its own component", async () => {
		const { nodes } = graphJsonToVueFlow({
			nodes: [{ id: "d", type: "decision", config: { question: "Q?", choices: ["A", "B"] } }],
			edges: [],
		});
		const w = mount(WorkflowCanvas, { props: { nodes } });
		await flushPromises();
		expect(w.findComponent(DecisionNode).exists()).toBe(true);
		expect(w.findComponent(UnknownNode).exists()).toBe(false);
	});

	it("offers a retry that emits upward when the load failed", async () => {
		const w = mount(WorkflowCanvas, { props: { isLoading: false, loadError: "boom" } });
		expect(w.text()).toContain("boom");
		await w.find(".retry-btn").trigger("click");
		expect(w.emitted("retry-load")).toHaveLength(1);
	});
});
