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
			title="Save agent"
			aria-label="Save agent"
			label="Save"
			@click="$emit('save')"
		>
			<ToolbarIcon name="save" />
		</ToolbarButton>

		<ToolbarButton
			v-if="isAdmin"
			class="primary"
			:disabled="isRunning"
			title="Execute agent"
			aria-label="Execute agent"
			:label="isRunning ? 'Running...' : 'Run'"
			@click="$emit('run')"
		>
			<ToolbarIcon v-if="!isRunning" name="play" />
			<ToolbarIcon v-else name="spinner" spin />
		</ToolbarButton>

		<ToolbarButton
			v-if="isAdmin"
			title="Schedule agent"
			aria-label="Schedule agent"
			label="Schedule"
			@click="$emit('schedule')"
		>
			<ToolbarIcon name="clock" />
		</ToolbarButton>

		<ToolbarButton
			v-if="isAdmin"
			title="Event triggers"
			aria-label="Event triggers"
			label="Triggers"
			@click="$emit('triggers')"
		>
			<ToolbarIcon name="bolt" />
		</ToolbarButton>

		<ToolbarButton
			v-if="isAdmin"
			:class="{ active: hasVariables }"
			title="Agent variables"
			aria-label="Agent variables"
			label="Variables"
			@click="$emit('variables')"
		>
			<ToolbarIcon name="tag" />
		</ToolbarButton>

		<ToolbarButton
			v-if="isAdmin && canShareTemplate"
			title="Share as template"
			aria-label="Share as template"
			label="Share"
			@click="$emit('share-template')"
		>
			<ToolbarIcon name="share" />
		</ToolbarButton>

		<ToolbarButton
			v-if="isAdmin"
			title="Agent settings"
			aria-label="Agent settings"
			label="Settings"
			@click="$emit('settings')"
		>
			<ToolbarIcon name="gear" />
		</ToolbarButton>

		<ToolbarButton
			:class="{ active: showRuns }"
			title="Run history"
			aria-label="Run history"
			label="Runs"
			@click="$emit('toggle-runs')"
		>
			<ToolbarIcon name="clipboard" />
		</ToolbarButton>

		<ToolbarButton
			:class="{ active: showAudit }"
			title="Audit summary"
			aria-label="Audit summary"
			label="Audit"
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
});

defineEmits([
	"save",
	"run",
	"schedule",
	"triggers",
	"settings",
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
			label: "Activate",
			icon: "play",
			btnClass: "primary",
			tooltip: "Activate: triggers and schedules will start running",
		};
	}
	if (s === "active") {
		return {
			label: "Pause",
			icon: "pause",
			btnClass: "warning",
			tooltip: "Pause: incoming triggers will be skipped, schedule paused",
		};
	}
	if (s === "paused") {
		return {
			label: "Resume",
			icon: "play",
			btnClass: "primary",
			tooltip: "Resume: triggers and schedules will start running again",
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
