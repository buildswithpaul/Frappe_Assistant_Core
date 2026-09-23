import { onMounted, onBeforeUnmount } from "vue";
import { useWorkflowStore } from "@/stores/workflowStore";

/**
 * Composable for subscribing to realtime workflow execution progress events
 * via Frappe's Socket.IO integration.
 *
 * Events emitted by the backend runner:
 * - workflow_progress: { type, run_name, node_id, status, ... }
 */
export function useWorkflowRealtime(workflowName) {
	const workflowStore = useWorkflowStore();
	let bound = false;

	function onProgress(data) {
		// Only process events for the current workflow
		if (data.workflow_name && data.workflow_name !== workflowName?.value) return;
		workflowStore.handleRunProgress(data);
	}

	onMounted(() => {
		if (window.frappe?.realtime?.on) {
			window.frappe.realtime.on("workflow_progress", onProgress);
			bound = true;
		}
	});

	onBeforeUnmount(() => {
		if (bound && window.frappe?.realtime?.off) {
			window.frappe.realtime.off("workflow_progress", onProgress);
			bound = false;
		}
	});

	return { onProgress };
}
