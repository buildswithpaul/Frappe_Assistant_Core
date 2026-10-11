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
	const triggers = ref([]);
	const isRefreshing = ref(false);

	const items = computed(() =>
		buildSetupChecklist({
			workflow: currentWorkflow.value,
			schedule: scheduleConfig.value,
			triggers: triggers.value,
			nodes: nodes.value,
			unapproved: preflight.checked.value ? preflight.warnings.value : null,
			checkError: preflight.error.value,
		})
	);
	const todoCount = computed(() => items.value.filter((i) => i.state === "todo").length);

	async function refresh() {
		if (!workflowId.value) return;
		isRefreshing.value = true;
		try {
			const [listed] = await Promise.all([
				api.workflows.triggers.list(workflowDisplayName.value, workflowId.value).catch(() => null),
				preflight.check(),
			]);
			triggers.value = listed?.triggers || [];
		} finally {
			isRefreshing.value = false;
		}
	}

	return { items, todoCount, isRefreshing, refresh };
}
