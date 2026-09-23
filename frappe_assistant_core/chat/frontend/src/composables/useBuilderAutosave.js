import { ref, onBeforeUnmount } from "vue";
import { createHistory } from "@/composables/useBuilderShortcuts";
import { graphJsonToVueFlow } from "@/components/workflows/graphUtils";
import { logger } from "@/utils/logger";

const AUTOSAVE_DELAY_MS = 2000;

/**
 * The builder's save pipeline: every graph mutation records an undo snapshot,
 * marks the workflow dirty and arms a debounced save. Undo/redo restore through
 * the same load path the server round trip uses, so there is no separate
 * inverse-operation model to keep correct.
 *
 * Owns `hasSaved` and `saveError` because it is what writes them; the loader and
 * the toolbar actions are handed the same refs.
 *
 * @param {object} deps - { workflowStore, workflowId, canEdit, nodes, edges,
 *                          globalSettings, selectedNode, toGraphJson,
 *                          checkLocally, checkOnServer }
 */
export function useBuilderAutosave({
	workflowStore,
	workflowId,
	canEdit,
	nodes,
	edges,
	globalSettings,
	selectedNode,
	toGraphJson,
	checkLocally,
	checkOnServer,
}) {
	const hasSaved = ref(false);
	const saveError = ref(null);

	const history = createHistory();
	let autoSaveTimer = null;
	let isApplyingHistory = false;

	function scheduleAutoSave() {
		if (!canEdit.value) return;
		if (!isApplyingHistory) history.record(toGraphJson());
		workflowStore.markDirty();
		if (autoSaveTimer) clearTimeout(autoSaveTimer);
		autoSaveTimer = setTimeout(save, AUTOSAVE_DELAY_MS);
	}

	async function save() {
		if (autoSaveTimer) clearTimeout(autoSaveTimer);
		if (!workflowId.value || !canEdit.value) return;

		checkLocally();

		try {
			await workflowStore.saveWorkflow(workflowId.value, { graph_json: toGraphJson() });
			hasSaved.value = true;
			saveError.value = null;
			await checkOnServer();
		} catch (err) {
			logger.error("Save failed:", err);
			saveError.value = err.message || "Save failed";
			workflowStore.markDirty();
		}
	}

	function applySnapshot(graphJson) {
		if (!graphJson || !canEdit.value) return;
		const parsed = graphJsonToVueFlow(graphJson);
		isApplyingHistory = true;
		nodes.value = parsed.nodes;
		edges.value = parsed.edges;
		globalSettings.value = parsed.globalSettings;
		selectedNode.value = null;
		scheduleAutoSave();
		isApplyingHistory = false;
	}

	/** Seed the buffer with the loaded graph — the load is not an undo step. */
	function resetHistory() {
		history.reset(toGraphJson());
	}

	onBeforeUnmount(() => {
		if (autoSaveTimer) clearTimeout(autoSaveTimer);
	});

	return {
		hasSaved,
		saveError,
		scheduleAutoSave,
		save,
		resetHistory,
		undo: () => applySnapshot(history.undo()),
		redo: () => applySnapshot(history.redo()),
	};
}
