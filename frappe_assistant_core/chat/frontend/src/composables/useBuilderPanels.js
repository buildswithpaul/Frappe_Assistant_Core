import { ref } from "vue";

/** Which rail panel, modal or popover the builder has open. */
export function useBuilderPanels() {
	const showRunsPanel = ref(false);
	const showAuditPanel = ref(false);
	const showScheduleModal = ref(false);
	const showVariablesModal = ref(false);
	const showShareModal = ref(false);
	const showTriggersModal = ref(false);
	const showSettingsDrawer = ref(false);
	const showSetup = ref(false);
	const focusRunName = ref("");

	// Runs and Audit share the right rail.
	function onToggleRuns() {
		showAuditPanel.value = false;
		showRunsPanel.value = !showRunsPanel.value;
	}

	function onToggleAudit() {
		showRunsPanel.value = false;
		showAuditPanel.value = !showAuditPanel.value;
	}

	/** A trigger firing's run: open Run history with that run expanded. */
	function onOpenRun(runName) {
		focusRunName.value = runName;
		showAuditPanel.value = false;
		showRunsPanel.value = true;
	}

	function onSetupAction(key, setup) {
		if (key === "recheck") return setup.refresh();
		showSetup.value = false;
		if (key === "schedule") showScheduleModal.value = true;
		if (key === "triggers") showTriggersModal.value = true;
		if (key === "settings") showSettingsDrawer.value = true;
	}

	/** Escape closes the checklist, then the settings drawer; false when neither was open. */
	function closeOnEscape() {
		if (showSetup.value) showSetup.value = false;
		else if (showSettingsDrawer.value) showSettingsDrawer.value = false;
		else return false;
		return true;
	}

	return {
		showRunsPanel,
		showAuditPanel,
		showScheduleModal,
		showVariablesModal,
		showShareModal,
		showTriggersModal,
		showSettingsDrawer,
		showSetup,
		focusRunName,
		onToggleRuns,
		onToggleAudit,
		onOpenRun,
		onSetupAction,
		closeOnEscape,
	};
}
