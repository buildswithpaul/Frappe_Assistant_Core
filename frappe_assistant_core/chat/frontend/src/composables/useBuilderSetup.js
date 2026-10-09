import { watch } from "vue";
import { useActivationPreflight } from "@/composables/useActivationPreflight";
import { useSetupChecklist } from "@/composables/useSetupChecklist";

/**
 * The builder's "is this agent ready to run unattended" state: the write-tool
 * preflight and the Setup checklist built on it. The checklist re-reads the
 * server each time it is opened so it never shows a stale answer.
 */
export function useBuilderSetup({
	workflowId,
	workflowDisplayName,
	currentWorkflow,
	scheduleConfig,
	nodes,
	isAdmin,
	showSetup,
}) {
	const preflight = useActivationPreflight({ nodes, currentWorkflow, isAdmin });
	const setup = useSetupChecklist({
		workflowId,
		workflowDisplayName,
		currentWorkflow,
		scheduleConfig,
		nodes,
		preflight,
	});

	watch(showSetup, (open) => {
		if (open) setup.refresh();
	});

	return { preflight, setup };
}
