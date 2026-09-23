<template>
	<div class="context-rail">
		<div class="rail-head">
			<div class="rail-label">Context · this conversation</div>
			<button
				v-if="collapsible"
				class="rail-collapse"
				aria-label="Hide context panel"
				title="Hide"
				@click="$emit('collapse')"
			>
				<svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
					<path d="M13 6l6 6-6 6M5 6l6 6-6 6" stroke="currentColor" stroke-width="2"
						stroke-linecap="round" stroke-linejoin="round" />
				</svg>
			</button>
		</div>

		<!-- Live tool-activity ticker for the current turn -->
		<ActivityTimeline v-if="artifacts.activity && artifacts.activity.length" :rows="artifacts.activity" />

		<!-- Task list (live status for the current turn) -->
		<TaskList v-if="artifacts.plan" :tasks="artifacts.plan.tasks" :live="live" />

		<!-- Pending approval (mirrors the in-thread card) -->
		<div v-if="artifacts.approval" class="rail-approval">
			<div class="rail-approval-head">
				<span class="rail-approval-dot" aria-hidden="true"></span>
				<span class="rail-approval-count">1 approval waiting</span>
			</div>
			<div class="rail-approval-body">
				<div class="rail-approval-title">{{ artifacts.approval.title }}</div>
				<div v-if="artifacts.approval.subtitle" class="rail-approval-sub mono">
					{{ artifacts.approval.subtitle }}
				</div>
				<button class="rail-approval-btn" @click="$emit('review-approval', artifacts.approval.id)">
					Review &amp; approve
				</button>
			</div>
		</div>

		<!-- Records & sources -->
		<div v-if="artifacts.records.length" class="rail-group">
			<div class="rail-group-label">Records &amp; sources</div>
			<div class="rail-chip-list">
				<div v-for="rec in artifacts.records" :key="rec.key" class="rail-chip">
					<span class="rail-chip-icon" aria-hidden="true">{{ rec.kind === "source" ? "📄" : "🗂" }}</span>
					<span class="rail-chip-label" :title="rec.label">{{ rec.label }}</span>
				</div>
			</div>
		</div>

		<!-- Generated charts -->
		<div v-if="artifacts.charts.length" class="rail-group">
			<div class="rail-group-label">Generated charts</div>
			<div class="rail-chip-list">
				<div v-for="c in artifacts.charts" :key="c.key" class="rail-chip">
					<span class="rail-chip-icon" aria-hidden="true">📊</span>
					<span class="rail-chip-label">{{ c.label }}</span>
				</div>
			</div>
		</div>

		<!-- Generated documents -->
		<div v-if="artifacts.documents.length" class="rail-group">
			<div class="rail-group-label">Created files</div>
			<div class="rail-chip-list">
				<a
					v-for="d in artifacts.documents"
					:key="d.key"
					class="rail-chip rail-chip-link"
					:href="d.url"
					target="_blank"
					rel="noopener"
				>
					<span class="rail-chip-icon" aria-hidden="true">📎</span>
					<span class="rail-chip-label" :title="d.label">{{ d.label }}</span>
					<span v-if="d.size" class="rail-chip-meta mono">{{ d.size }}</span>
				</a>
			</div>
		</div>
	</div>
</template>

<script setup>
import ActivityTimeline from "./rail/ActivityTimeline.vue";
import TaskList from "./rail/TaskList.vue";

defineProps({
	artifacts: {
		type: Object,
		required: true,
	},
	// When true, render a collapse control in the header (docked rail only —
	// the tab/sheet overlays own their own close affordance).
	collapsible: {
		type: Boolean,
		default: false,
	},
	// False once the turn has finished — the rail then stops presenting tasks
	// and activity as work still in progress.
	live: {
		type: Boolean,
		default: true,
	},
});
defineEmits(["review-approval", "collapse"]);
</script>

<style scoped>
.context-rail {
	display: flex;
	flex-direction: column;
	gap: 14px;
	padding: 16px;
	background: var(--ql-surface, #ffffff);
	border-left: 1px solid var(--ql-border, #ece9e3);
	height: 100%;
	overflow-y: auto;
}
.mono {
	font-variant-numeric: tabular-nums;
	font-family: ui-monospace, "SF Mono", "Cascadia Code", monospace;
}
.rail-head {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 8px;
}
.rail-label {
	font-size: 10px;
	text-transform: uppercase;
	letter-spacing: 0.08em;
	color: var(--ql-text-muted, #8a857c);
}
.rail-collapse {
	display: flex;
	align-items: center;
	justify-content: center;
	flex-shrink: 0;
	width: 22px;
	height: 22px;
	margin: -2px -2px -2px 0;
	border: none;
	border-radius: 6px;
	background: transparent;
	color: var(--ql-text-muted, #8a857c);
	cursor: pointer;
}
.rail-collapse:hover {
	background: var(--ql-bg, #fbfaf8);
	color: var(--ql-text-secondary, #57534c);
}

/* ---- Pending approval mini-card ---- */
.rail-approval {
	border: 1px solid var(--ql-gold-soft);
	border-radius: 10px;
	overflow: hidden;
}
.rail-approval-head {
	background: var(--ql-gold-soft);
	padding: 8px 11px;
	display: flex;
	align-items: center;
	gap: 7px;
	border-bottom: 1px solid var(--ql-gold-soft);
}
.rail-approval-dot {
	width: 7px;
	height: 7px;
	border-radius: 50%;
	background: var(--ql-gold, #c9a227);
	box-shadow: 0 0 0 3px rgba(201, 162, 39, 0.2);
}
.rail-approval-count {
	font-size: 11px;
	font-weight: 600;
	color: var(--ql-text, #1a1a17);
}
.rail-approval-body {
	padding: 9px 11px;
}
.rail-approval-title {
	font-size: 11.5px;
	font-weight: 600;
	color: var(--ql-text, #1a1a17);
}
.rail-approval-sub {
	font-size: 10.5px;
	color: var(--ql-text-muted, #8a857c);
	margin-top: 1px;
}
.rail-approval-btn {
	margin-top: 7px;
	width: 100%;
	font-size: 11px;
	font-weight: 600;
	padding: 5px 11px;
	border-radius: 7px;
	background: var(--ql-accent, #0f6e5c);
	color: #fff;
	border: none;
	cursor: pointer;
}
.rail-approval-btn:hover {
	background: var(--ql-accent-hover, #0b5a4b);
}

/* ---- Groups / chips ---- */
.rail-group-label {
	font-size: 11px;
	color: var(--ql-text-muted, #8a857c);
	margin-bottom: 6px;
}
.rail-chip-list {
	display: flex;
	flex-direction: column;
	gap: 5px;
}
.rail-chip {
	display: flex;
	align-items: center;
	gap: 7px;
	font-size: 11.5px;
	color: var(--ql-text, #1a1a17);
	padding: 6px 8px;
	border: 1px solid var(--ql-border, #ece9e3);
	border-radius: 7px;
	background: var(--ql-bg, #fbfaf8);
	text-decoration: none;
}
.rail-chip-link:hover {
	border-color: var(--ql-border-hover, #dedad2);
}
.rail-chip-label {
	flex: 1;
	min-width: 0;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}
.rail-chip-meta {
	flex-shrink: 0;
	font-size: 10px;
	color: var(--ql-text-muted, #8a857c);
}
</style>
