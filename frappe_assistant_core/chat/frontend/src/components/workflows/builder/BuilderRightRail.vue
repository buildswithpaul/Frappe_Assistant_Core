<template>
	<!-- Config, Runs and Audit share the right rail; Audit yields to Runs. -->
	<NodeConfigPanel
		v-if="selectedNode"
		:node="selectedNode"
		:variables="variables"
		:runtime-user-label="runtimeUserLabel"
		:readonly="readonly"
		@update="(nodeId, updates) => $emit('node-update', nodeId, updates)"
		@delete="(nodeId) => $emit('node-delete', nodeId)"
		@close="$emit('close-config')"
		@request-save="$emit('request-save')"
	/>

	<RunHistoryPanel v-if="showRuns" :workflow-id="workflowId" @close="$emit('close-runs')" />

	<AgentAuditPanel
		v-if="showAudit && !showRuns"
		:workflow-id="workflowId"
		@close="$emit('close-audit')"
	/>
</template>

<script setup>
import NodeConfigPanel from "@/components/workflows/NodeConfigPanel.vue";
import RunHistoryPanel from "@/components/workflows/RunHistoryPanel.vue";
import AgentAuditPanel from "@/components/workflows/audit/AgentAuditPanel.vue";

defineProps({
	selectedNode: { type: Object, default: null },
	/** Workflow-level global_settings.variables — feeds the prompt preview. */
	variables: { type: Object, default: () => ({}) },
	runtimeUserLabel: { type: String, default: "" },
	readonly: { type: Boolean, default: false },
	showRuns: { type: Boolean, default: false },
	showAudit: { type: Boolean, default: false },
	workflowId: { type: String, default: "" },
});

defineEmits([
	"node-update",
	"node-delete",
	"close-config",
	"request-save",
	"close-runs",
	"close-audit",
]);
</script>
