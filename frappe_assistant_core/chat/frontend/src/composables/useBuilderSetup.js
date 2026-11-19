import { ref, watch } from "vue";
import { api } from "@/api/client";
import { __ } from "@/utils/i18n";
import { logger } from "@/utils/logger";
import { useActivationPreflight } from "@/composables/useActivationPreflight";
import { useSetupChecklist } from "@/composables/useSetupChecklist";

/**
 * The builder's "is this agent ready to run unattended" state: the write-tool
 * preflight, the setup checklist built on it, and the panel's own actions.
 */
export function useBuilderSetup({
	workflowId,
	workflowDisplayName,
	currentWorkflow,
	scheduleConfig,
	nodes,
	isAdmin,
	panels,
}) {
	const { showSetup, showTriggersModal } = panels;
	const preflight = useActivationPreflight({ nodes, currentWorkflow, isAdmin });
	const setup = useSetupChecklist({
		workflowId,
		workflowDisplayName,
		currentWorkflow,
		scheduleConfig,
		nodes,
		preflight,
	});
	const stuckTools = ref([]);
	const writeNote = ref("");

	watch(showSetup, (open) => {
		if (open) setup.refresh();
	});
	// Closing the Triggers modal may have added, changed or removed one.
	watch(showTriggersModal, (open, wasOpen) => {
		if (wasOpen && !open) setup.refresh();
	});

	/** On arrival, an unfinished agent shows its setup instead of hiding it. */
	function openIfUnfinished() {
		if (currentWorkflow.value?.status !== "Active" && setup.blockReason.value) showSetup.value = true;
	}

	/**
	 * Approve one of the signed-in user's own write tools. AR may store the
	 * preference under a server-prefixed name this page cannot see, so the
	 * re-check decides: a tool that still reads as not allowed falls back to
	 * the Settings → Connections instruction.
	 */
	async function allowTool(warning) {
		writeNote.value = "";
		try {
			await api.tools.setPreference(warning.tool, "always_allow");
			const after = await preflight.check();
			if (after.some((w) => w.tool === warning.tool)) {
				stuckTools.value = [...stuckTools.value, warning.tool];
				writeNote.value = __("{0} still won't run unattended. Set it to Always allow in Settings → Connections.", [
					warning.tool,
				]);
			}
		} catch (err) {
			logger.error("Allow tool failed:", err);
			writeNote.value = err.message || __("Couldn't save the tool permission");
		}
	}

	return { preflight, setup, stuckTools, writeNote, openIfUnfinished, allowTool };
}
