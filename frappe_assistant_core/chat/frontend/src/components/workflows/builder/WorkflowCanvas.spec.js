import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { ref, computed, h } from "vue";
import { createPinia, setActivePinia } from "pinia";
import WorkflowCanvas from "@/components/workflows/builder/WorkflowCanvas.vue";
import { useWorkflowGraphActions } from "@/composables/useWorkflowGraphActions";

setActivePinia(createPinia());
window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });

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

	it("offers a retry that emits upward when the load failed", async () => {
		const w = mount(WorkflowCanvas, { props: { isLoading: false, loadError: "boom" } });
		expect(w.text()).toContain("boom");
		await w.find(".retry-btn").trigger("click");
		expect(w.emitted("retry-load")).toHaveLength(1);
	});
});
