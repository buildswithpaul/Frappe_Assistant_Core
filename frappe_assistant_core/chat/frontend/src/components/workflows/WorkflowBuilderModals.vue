<template>
	<div>
		<!-- Run Input Modal -->
		<RunInputModal
			:model-value="showRun"
			:is-running="isRunning"
			@update:model-value="$emit('update:show-run', $event)"
			@confirm="(inputText) => $emit('run-confirm', inputText)"
		/>

		<!-- Schedule Modal -->
		<ScheduleModal
			:model-value="showSchedule"
			:config="scheduleConfig"
			:is-saving="isSettingSchedule"
			@update:model-value="$emit('update:show-schedule', $event)"
			@save="(config) => $emit('schedule-save', config)"
		/>

		<!-- Variables Modal -->
		<VariablesModal
			:model-value="showVariables"
			:variables="variables"
			@update:model-value="$emit('update:show-variables', $event)"
			@save="(vars) => $emit('variables-save', vars)"
		/>

		<!-- Share as Template Modal — gated by marketplace user-publishing flag -->
		<!-- The marketplace looks the workflow up by docname, so the id — never
		     the display name — is what travels. -->
		<ShareTemplateModal
			v-if="userStore.userPublishingEnabled"
			:model-value="showShare"
			:workflow-id="workflowId"
			:workflow-display-name="workflowDisplayName"
			@update:model-value="$emit('update:show-share', $event)"
			@shared="$emit('template-shared')"
		/>

		<!-- Event Triggers Modal -->
		<TriggersModal
			:model-value="showTriggers"
			:workflow-id="workflowId"
			:workflow-display-name="workflowDisplayName"
			@update:model-value="$emit('update:show-triggers', $event)"
		/>
	</div>
</template>

<script setup>
import RunInputModal from "@/components/workflows/RunInputModal.vue";
import ScheduleModal from "@/components/workflows/ScheduleModal.vue";
import VariablesModal from "@/components/workflows/VariablesModal.vue";
import ShareTemplateModal from "@/components/workflows/ShareTemplateModal.vue";
import TriggersModal from "@/components/workflows/triggers/TriggersModal.vue";
import { useUserStore } from "@/stores/userStore";

const userStore = useUserStore();

defineProps({
	// Run input modal
	showRun: { type: Boolean, default: false },
	isRunning: { type: Boolean, default: false },
	// Schedule modal
	showSchedule: { type: Boolean, default: false },
	scheduleConfig: { type: Object, required: true },
	isSettingSchedule: { type: Boolean, default: false },
	// Variables modal
	showVariables: { type: Boolean, default: false },
	variables: { type: Object, default: () => ({}) },
	// Share template modal
	showShare: { type: Boolean, default: false },
	/** The AR Workflow docname (WF-#####) — the authoritative id. */
	workflowId: { type: String, default: "" },
	workflowDisplayName: { type: String, default: "" },
	// Triggers modal
	showTriggers: { type: Boolean, default: false },
});

defineEmits([
	"update:show-run",
	"update:show-schedule",
	"update:show-variables",
	"update:show-share",
	"update:show-triggers",
	"run-confirm",
	"schedule-save",
	"variables-save",
	"template-shared",
]);
</script>
