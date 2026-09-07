import { ref } from "vue";
import { logger } from "@/utils/logger";

/**
 * The two ways an agent is set going: a run started by hand, and the schedule
 * that starts it later. Neither is a save, so failures surface on `actionError`
 * rather than on the save banner.
 *
 * @param {object} deps - { workflowStore, workflowId, canEdit, isDirty, nodes,
 *                          save, checkBeforeRun, scheduleConfig, showRunsPanel,
 *                          showScheduleModal }
 */
export function useWorkflowExecution({
	workflowStore,
	workflowId,
	canEdit,
	isDirty,
	nodes,
	save,
	checkBeforeRun,
	scheduleConfig,
	showRunsPanel,
	showScheduleModal,
}) {
	const actionError = ref(null);
	const isSettingSchedule = ref(false);
	const showRunModal = ref(false);

	/** A graph with an input node asks for its input before it runs. */
	function requestRun() {
		if (!canEdit.value) return;
		if (nodes.value.some((n) => n.type === "workflow-input")) showRunModal.value = true;
		else confirmRun();
	}

	async function confirmRun(inputText = "") {
		showRunModal.value = false;
		if (!canEdit.value) return;
		if (!checkBeforeRun()) return;
		if (isDirty.value) await save();

		try {
			await workflowStore.executeWorkflow(workflowId.value, inputText.trim() || null);
			showRunsPanel.value = true;
		} catch (err) {
			logger.error("Execution failed:", err);
			actionError.value = err.message || "Could not start the run";
		}
	}

	async function saveSchedule(config) {
		if (!workflowId.value || !config.cron.trim() || !canEdit.value) return;
		isSettingSchedule.value = true;
		try {
			scheduleConfig.value = { ...config };
			await workflowStore.setSchedule(
				workflowId.value,
				config.cron.trim(),
				config.timezone,
				config.enabled,
				config.defaultInput.trim() || null
			);
			showScheduleModal.value = false;
		} catch (err) {
			logger.error("Schedule failed:", err);
			actionError.value = err.message || "Failed to save the schedule";
		} finally {
			isSettingSchedule.value = false;
		}
	}

	return {
		actionError,
		isSettingSchedule,
		showRunModal,
		requestRun,
		confirmRun,
		saveSchedule,
	};
}
