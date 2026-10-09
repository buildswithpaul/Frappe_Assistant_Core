import { ref } from "vue";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";
import { __ } from "@/utils/i18n";
import { useToast } from "@/composables/useToast";

const NEXT_STATUS = { Draft: "Active", Active: "Paused", Paused: "Active" };

/**
 * The workflow-document actions the toolbar drives — status toggle, rename and
 * the settings drawer's save. All three write non-graph fields through the same
 * `saveWorkflow` the autosave uses, so the first two report on the same
 * `saveError`; the drawer keeps its own so a failure stays next to the form.
 *
 * @param {object} deps - { workflowStore, workflowId, currentWorkflow, canEdit,
 *                          isDirty, toGraphJson, hasSaved, saveError, preflight }
 */
export function useWorkflowActions({
	workflowStore,
	workflowId,
	currentWorkflow,
	canEdit,
	isDirty,
	toGraphJson,
	hasSaved,
	saveError,
	preflight,
	notify = (message) => useToast().showToast(message, "info", 6000),
}) {
	const settingsError = ref(null);
	const pendingActivation = ref(false);
	const isCheckingActivation = ref(false);

	async function toggleStatus() {
		if (!workflowId.value || !canEdit.value) return;
		const nextStatus = NEXT_STATUS[currentWorkflow.value?.status];
		if (!nextStatus) return;

		const updates = { status: nextStatus };
		if (isDirty.value) updates.graph_json = toGraphJson();

		try {
			await workflowStore.saveWorkflow(workflowId.value, updates);
			hasSaved.value = true;
			saveError.value = null;
		} catch (err) {
			logger.error("Status toggle failed:", err);
			saveError.value = err.message || __("Failed to switch to {0}", [nextStatus]);
		}
	}

	/** Activate and Resume check the write tools first; Pause never waits. */
	async function requestToggleStatus() {
		if (!workflowId.value || !canEdit.value) return;
		if (isCheckingActivation.value) return;
		if (NEXT_STATUS[currentWorkflow.value?.status] !== "Active") return toggleStatus();
		isCheckingActivation.value = true;
		try {
			const warnings = await preflight.check();
			if (warnings.length) {
				pendingActivation.value = true;
				return;
			}
			if (preflight.error?.value) {
				notify(__("Couldn't check which write tools are approved; activating anyway."));
			}
		} finally {
			isCheckingActivation.value = false;
		}
		return toggleStatus();
	}

	async function confirmActivation() {
		pendingActivation.value = false;
		await toggleStatus();
	}

	function cancelActivation() {
		pendingActivation.value = false;
	}

	async function rename(newName) {
		if (!workflowId.value || !canEdit.value) return;
		try {
			// Triggers bind to this workflow; warn before the display name moves
			// under them.
			const existing = await api.workflows.triggers
				.list(currentWorkflow.value?.workflow_name, workflowId.value)
				.catch(() => null);
			const count = existing?.triggers?.length || 0;
			if (
				count &&
				!window.confirm(
					__("{0} event trigger(s) point at this agent. Renaming it does not move them — continue?", [
						count,
					])
				)
			) {
				return;
			}
			await workflowStore.saveWorkflow(workflowId.value, { workflow_name: newName });
			saveError.value = null;
		} catch (err) {
			logger.error("Rename failed:", err);
			saveError.value = err.message || __("Rename failed");
		}
	}

	/** Resolves true when the drawer may close. */
	async function saveSettings(fields) {
		if (!workflowId.value || !canEdit.value) return false;
		settingsError.value = null;
		try {
			await workflowStore.saveWorkflow(workflowId.value, fields);
			return true;
		} catch (err) {
			logger.error("Settings save failed:", err);
			settingsError.value = err.message || __("Failed to save settings");
			return false;
		}
	}

	return {
		settingsError,
		toggleStatus,
		requestToggleStatus,
		pendingActivation,
		isCheckingActivation,
		confirmActivation,
		cancelActivation,
		rename,
		saveSettings,
	};
}
