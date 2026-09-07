<template>
	<div class="workflow-toolbar" role="toolbar" aria-label="Agent actions">
		<WorkflowTitle
			:name="name"
			:status="status"
			:can-rename="isAdmin"
			@back="$emit('back')"
			@rename="$emit('rename', $event)"
		/>

		<div class="toolbar-center">
			<span v-if="isDirty" class="dirty-dot" title="Unsaved changes"></span>
			<span v-if="isSaving" class="save-indicator">Saving...</span>
			<span v-else-if="!isDirty && lastSaved" class="save-indicator saved">Saved</span>
		</div>

		<WorkflowToolbarActions
			:status="status"
			:is-admin="isAdmin"
			:can-share-template="userPublishingEnabled"
			:is-dirty="isDirty"
			:is-saving="isSaving"
			:is-running="isRunning"
			:show-runs="showRuns"
			:show-audit="showAudit"
			:has-variables="hasVariables"
			@save="$emit('save')"
			@run="$emit('run')"
			@schedule="$emit('schedule')"
			@triggers="$emit('triggers')"
			@settings="$emit('settings')"
			@variables="$emit('variables')"
			@share-template="$emit('share-template')"
			@toggle-runs="$emit('toggle-runs')"
			@toggle-audit="$emit('toggle-audit')"
			@toggle-status="$emit('toggle-status')"
		/>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { useUserStore } from "@/stores/userStore";
import WorkflowTitle from "@/components/workflows/toolbar/WorkflowTitle.vue";
import WorkflowToolbarActions from "@/components/workflows/toolbar/WorkflowToolbarActions.vue";

defineProps({
	name: { type: String, default: "" },
	status: { type: String, default: "" },
	isDirty: { type: Boolean, default: false },
	isSaving: { type: Boolean, default: false },
	isRunning: { type: Boolean, default: false },
	showRuns: { type: Boolean, default: false },
	showAudit: { type: Boolean, default: false },
	lastSaved: { type: Boolean, default: false },
	hasVariables: { type: Boolean, default: false },
});

defineEmits([
	"back",
	"save",
	"run",
	"schedule",
	"triggers",
	"settings",
	"toggle-runs",
	"toggle-audit",
	"toggle-status",
	"rename",
	"variables",
	"share-template",
]);

const userStore = useUserStore();
const isAdmin = computed(() => userStore.isAdmin);
const userPublishingEnabled = computed(() => userStore.userPublishingEnabled);
</script>

<style scoped>
.workflow-toolbar {
	display: flex;
	align-items: center;
	justify-content: space-between;
	height: var(--ql-topbar-height, 3.5rem);
	padding: 0 1rem;
	background: var(--ql-surface);
	border-bottom: 1px solid var(--ql-border);
	flex-shrink: 0;
	gap: 1rem;
}

.toolbar-center {
	flex-shrink: 0;
	display: flex;
	align-items: center;
	gap: 0.375rem;
}

.dirty-dot {
	width: 6px;
	height: 6px;
	border-radius: 50%;
	background: var(--ql-warning);
}

.save-indicator {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.save-indicator.saved {
	color: var(--ql-success);
}
</style>
