<template>
	<div class="trigger-card" :class="{ disabled: !trigger.enabled }">
		<div class="header">
			<div class="title-row">
				<span class="title">{{ trigger.title }}</span>
				<span class="status-chip" :class="trigger.enabled ? 'chip-on' : 'chip-off'">
					{{ trigger.enabled ? "Enabled" : "Disabled" }}
				</span>
			</div>
			<div class="actions">
				<button class="icon-btn" title="View log" @click="$emit('view-log', trigger)">
					Log
				</button>
				<button
					class="icon-btn"
					:title="trigger.enabled ? 'Disable' : 'Enable'"
					@click="$emit('toggle', trigger)"
				>
					{{ trigger.enabled ? "Disable" : "Enable" }}
				</button>
				<button class="icon-btn" title="Edit" @click="$emit('edit', trigger)">Edit</button>
				<button class="icon-btn danger" title="Delete" @click="$emit('delete', trigger)">
					Delete
				</button>
			</div>
		</div>
		<div class="body">
			<div class="field">
				<span class="label">When</span>
				<span class="value">
					<code>{{ trigger.doctype_event }}</code> on
					<code>{{ trigger.reference_doctype }}</code>
				</span>
			</div>
			<div v-if="trigger.changed_fields" class="field">
				<span class="label">Only if changed</span>
				<span class="value mono">{{ trigger.changed_fields }}</span>
			</div>
			<div class="field">
				<span class="label">Stats</span>
				<span class="value">
					Fired <strong>{{ trigger.fire_count || 0 }}</strong> times
					<template v-if="trigger.last_fired_at">
						— last at {{ formatDate(trigger.last_fired_at) }}
					</template>
				</span>
			</div>
			<div v-if="trigger.last_error" class="field error-field">
				<span class="label">Last error</span>
				<span class="value error">{{ trigger.last_error }}</span>
			</div>
		</div>
	</div>
</template>

<script setup>
defineProps({
	trigger: { type: Object, required: true },
});

defineEmits(["edit", "delete", "toggle", "view-log"]);

function formatDate(s) {
	if (!s) return "";
	try {
		return new Date(s).toLocaleString();
	} catch {
		return s;
	}
}
</script>

<style scoped>
.trigger-card {
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	padding: 0.75rem;
	background: var(--ql-bg);
	color: var(--ql-text);
}
.trigger-card.disabled {
	opacity: 0.6;
}
.header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 0.5rem;
	margin-bottom: 0.5rem;
}
.title-row {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	min-width: 0;
}
.title {
	font-weight: 600;
	font-size: 0.875rem;
	color: var(--ql-text);
	overflow: hidden;
	text-overflow: ellipsis;
}
.status-chip {
	font-size: 0.6875rem;
	padding: 0.125rem 0.5rem;
	border-radius: 0.625rem;
	font-weight: 500;
}
.chip-on {
	background: color-mix(in srgb, var(--ql-success) 18%, transparent);
	color: var(--ql-success);
}
.chip-off {
	background: var(--ql-subtle);
	color: var(--ql-text-secondary);
}
.actions {
	display: flex;
	gap: 0.25rem;
	flex-shrink: 0;
}
.icon-btn {
	padding: 0.25rem 0.625rem;
	font-size: 0.75rem;
	border: 1px solid var(--ql-border);
	background: var(--ql-surface);
	color: var(--ql-text);
	border-radius: 0.25rem;
	cursor: pointer;
	transition: background 0.15s ease;
}
.icon-btn:hover {
	background: var(--ql-subtle);
}
.icon-btn.danger {
	color: var(--ql-danger);
	border-color: color-mix(in srgb, var(--ql-danger) 40%, transparent);
}
.icon-btn.danger:hover {
	background: color-mix(in srgb, var(--ql-danger) 12%, transparent);
}
.body {
	display: flex;
	flex-direction: column;
	gap: 0.25rem;
	font-size: 0.75rem;
}
.field {
	display: flex;
	gap: 0.5rem;
}
.label {
	color: var(--ql-text-secondary);
	min-width: 6.25rem;
}
.value {
	flex: 1;
	color: var(--ql-text);
}
.value.mono {
	font-family: "SF Mono", Monaco, monospace;
}
.value.error {
	color: var(--ql-danger);
}
.error-field .value {
	word-break: break-word;
}
code {
	background: var(--ql-subtle);
	color: var(--ql-text);
	padding: 0.0625rem 0.375rem;
	border-radius: 0.1875rem;
	font-size: 0.6875rem;
}
</style>
