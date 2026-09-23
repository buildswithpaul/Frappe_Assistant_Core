import { ref } from "vue";
import { graphJsonToVueFlow } from "@/components/workflows/graphUtils";

/** Frappe Check fields arrive as 0/1 integers — `!== false` is always true. */
function isChecked(value) {
	return Number(value) === 1;
}

/**
 * Read a workflow's schedule off the get_workflow payload.
 *
 * AR returns `timezone` (never `schedule_timezone`) and `schedule_enabled` as
 * an int. Reading the wrong key silently pinned every schedule to UTC, and
 * coercing the int with `!== false` re-enabled paused ones — so reopening the
 * modal and pressing Save moved a paused 09:00 Asia/Kolkata job to a live
 * 09:00 UTC one.
 */
export function scheduleFromWorkflow(result = {}) {
	return {
		cron: result.cron_expression || "",
		timezone: result.timezone || "UTC",
		defaultInput: result.default_input || "",
		enabled: isChecked(result.schedule_enabled),
	};
}

/**
 * Load a workflow and hydrate the canvas refs (nodes, edges, globalSettings) plus
 * schedule config. Exposes isLoading/loadError plus a `loadCurrentWorkflow` callable
 * the parent can bind to a retry button and invoke from onMounted.
 *
 * All reactive targets are owned by the parent and passed in — this composable
 * doesn't hold canvas state, it just populates caller-owned refs.
 *
 * @param {object} deps - { workflowStore, workflowId, nodes, edges, globalSettings,
 *                           hasSaved, scheduleConfig }
 */
export function useWorkflowLoader(deps) {
	const { workflowStore, workflowId, nodes, edges, globalSettings, hasSaved, scheduleConfig } =
		deps;

	const isLoading = ref(false);
	const loadError = ref(null);

	async function loadCurrentWorkflow() {
		if (!workflowId.value) return;
		isLoading.value = true;
		loadError.value = null;
		try {
			const result = await workflowStore.loadWorkflow(workflowId.value);
			const parsed = graphJsonToVueFlow(result.graph_json);
			nodes.value = parsed.nodes;
			edges.value = parsed.edges;
			globalSettings.value = parsed.globalSettings;
			hasSaved.value = !!result.graph_json;
			// Hydrated unconditionally: guarding on cron_expression left a
			// cleared schedule showing the previous workflow's values.
			scheduleConfig.value = scheduleFromWorkflow(result);
		} catch (err) {
			loadError.value = err.message || "Failed to load agent";
		} finally {
			isLoading.value = false;
		}
	}

	return { isLoading, loadError, loadCurrentWorkflow };
}
