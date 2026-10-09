import { ref, computed } from "vue";
import { api } from "@/api/client";
import { buildSetupChecklist } from "@/components/workflows/builder/setupChecklist";

export function useSetupChecklist({
	workflowId,
	workflowDisplayName,
	currentWorkflow,
	scheduleConfig,
	nodes,
	preflight,
}) {
	const enabledTriggerCount = ref(0);
	const isRefreshing = ref(false);

	const items = computed(() =>
		buildSetupChecklist({
			workflow: currentWorkflow.value,
			schedule: scheduleConfig.value,
			enabledTriggerCount: enabledTriggerCount.value,
			nodes: nodes.value,
			unapproved: preflight.checked.value ? preflight.warnings.value : null,
		})
	);
	const todoCount = computed(() => items.value.filter((i) => i.state === "todo").length);

	async function refresh() {
		if (!workflowId.value) return;
		isRefreshing.value = true;
		try {
			const [triggers] = await Promise.all([
				api.workflows.triggers.list(workflowDisplayName.value, workflowId.value).catch(() => null),
				preflight.check(),
			]);
			enabledTriggerCount.value = (triggers?.triggers || []).filter(
				(t) => Number(t.enabled) === 1
			).length;
		} finally {
			isRefreshing.value = false;
		}
	}

	return { items, todoCount, isRefreshing, refresh };
}
