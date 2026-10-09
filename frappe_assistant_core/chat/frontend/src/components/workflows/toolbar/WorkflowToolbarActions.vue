<template>
	<div class="toolbar-right">
		<!-- Activate / Pause / Resume — toggles workflow.status server-side. Hidden on Archived. -->
		<ToolbarButton
			v-if="isAdmin && statusToggle"
			:class="statusToggle.btnClass"
			:disabled="isSaving || isRunning"
			:title="statusToggle.tooltip"
			:aria-label="statusToggle.label"
			:label="statusToggle.label"
			@click="$emit('toggle-status')"
		>
			<ToolbarIcon :name="statusToggle.icon" />
		</ToolbarButton>

		<ToolbarButton
			v-if="isAdmin"
			:class="{ accent: isDirty }"
			:disabled="isSaving || !isDirty"
			:title="__('Save agent')"
			:aria-label="__('Save agent')"
			:label="__('Save')"
			@click="$emit('save')"
		>
			<ToolbarIcon name="save" />
		</ToolbarButton>

		<ToolbarButton
			v-if="isAdmin"
			class="primary"
			:disabled="isRunning || !canRun"
			:title="!canRun && runBlockReason ? runBlockReason : __('Run agent')"
			:aria-label="__('Run agent')"
			:label="isRunning ? __('Running...') : __('Run')"
			@click="$emit('run')"
		>
			<ToolbarIcon v-if="!isRunning" name="play" />
			<ToolbarIcon v-else name="spinner" spin />
		</ToolbarButton>

		<ToolbarButton
			v-if="isAdmin"
			:class="{ accent: setupTodo > 0 }"
			:title="__('Setup checklist')"
			:aria-label="setupTodo ? __('Setup checklist, {0} to do', [setupTodo]) : __('Setup checklist')"
			:label="setupTodo ? __('Setup ({0})', [setupTodo]) : __('Setup')"
			@click="$emit('setup')"
		>
			<ToolbarIcon name="gear" />
		</ToolbarButton>

		<ToolbarButton
			v-if="isAdmin"
			:class="{ active: hasVariables }"
			:title="__('Agent variables')"
			:aria-label="__('Agent variables')"
			:label="__('Variables')"
			@click="$emit('variables')"
		>
			<ToolbarIcon name="tag" />
		</ToolbarButton>

		<ToolbarButton
			v-if="isAdmin && canShareTemplate"
			:title="__('Share as template')"
			:aria-label="__('Share as template')"
			:label="__('Share')"
			@click="$emit('share-template')"
		>
			<ToolbarIcon name="share" />
		</ToolbarButton>

		<ToolbarButton
			:class="{ active: showRuns }"
			:title="__('Run history')"
			:aria-label="__('Run history')"
			:label="__('Runs')"
			@click="$emit('toggle-runs')"
		>
			<ToolbarIcon name="clipboard" />
		</ToolbarButton>

		<ToolbarButton
			:class="{ active: showAudit }"
			:title="__('Audit summary')"
			:aria-label="__('Audit summary')"
			:label="__('Audit')"
			@click="$emit('toggle-audit')"
		>
			<ToolbarIcon name="chart" />
		</ToolbarButton>
	</div>
</template>

<script setup>
import { computed } from "vue";
import ToolbarButton from "./ToolbarButton.vue";
import ToolbarIcon from "./ToolbarIcon.vue";
import { __ } from "@/utils/i18n";

const props = defineProps({
	status: { type: String, default: "" },
	isAdmin: { type: Boolean, default: false },
	canShareTemplate: { type: Boolean, default: false },
	isDirty: { type: Boolean, default: false },
	isSaving: { type: Boolean, default: false },
	isRunning: { type: Boolean, default: false },
	showRuns: { type: Boolean, default: false },
	showAudit: { type: Boolean, default: false },
	hasVariables: { type: Boolean, default: false },
	canRun: { type: Boolean, default: true },
	runBlockReason: { type: String, default: "" },
	setupTodo: { type: Number, default: 0 },
});

defineEmits([
	"save",
	"run",
	"setup",
	"variables",
	"share-template",
	"toggle-runs",
	"toggle-audit",
	"toggle-status",
]);

// Drives the Activate / Pause / Resume button. Returns null for Archived
// (no toggle — those workflows are read-only history).
const statusToggle = computed(() => {
	const s = props.status?.toLowerCase();
	if (s === "draft") {
		return {
			label: __("Activate"),
			icon: "play",
			btnClass: "primary",
			tooltip: __("Activate: triggers and schedules will start running"),
		};
	}
	if (s === "active") {
		return {
			label: __("Pause"),
			icon: "pause",
			btnClass: "warning",
			tooltip: __("Pause: incoming triggers will be skipped, schedule paused"),
		};
	}
	if (s === "paused") {
		return {
			label: __("Resume"),
			icon: "play",
			btnClass: "primary",
			tooltip: __("Resume: triggers and schedules will start running again"),
		};
	}
	return null;
});
</script>

<style scoped>
.toolbar-right {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	flex-shrink: 0;
}
</style>
