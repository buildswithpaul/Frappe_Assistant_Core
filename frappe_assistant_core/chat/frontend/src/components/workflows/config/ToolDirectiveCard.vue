<template>
	<div class="tool-card" :class="{ missing: resolution?.status === 'missing' }">
		<div class="tool-card-header">
			<span class="tool-card-name" :title="directive.tool_name">{{
				directive.tool_name
			}}</span>

			<span class="resolution-badge" :class="badge.tone" :title="badge.title">
				<span class="badge-dot"></span>{{ badge.label }}
			</span>

			<button
				class="priority-pill"
				:class="priority"
				:disabled="readonly"
				:title="
					priority === 'primary'
						? 'Preferred — the prompt tells the model to use this tool'
						: 'Optional — the prompt offers this tool as a fallback'
				"
				@click.stop="$emit('toggle-priority')"
			>
				{{ priority === "primary" ? "Preferred" : "Optional" }}
			</button>

			<button
				v-if="!readonly"
				class="remove-tool-btn"
				title="Remove tool"
				aria-label="Remove tool"
				@click.stop="$emit('remove')"
			>
				<svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M6 18L18 6M6 6l12 12"
					/>
				</svg>
			</button>
		</div>

		<div class="tool-card-subtitle">
			<span v-if="server" class="tool-server-badge">{{ server }}</span>
			<span v-if="directive.description" class="tool-card-desc">{{
				directive.description
			}}</span>
		</div>

		<label class="tool-required">
			<input
				type="checkbox"
				:checked="!!directive.required"
				:disabled="readonly"
				@change="$emit('toggle-required', $event.target.checked)"
			/>
			<span>Required — stop the run if this tool is unavailable</span>
		</label>

		<p v-if="resolution?.status === 'missing'" class="tool-card-warning">
			Not available to the agent's runtime user.
			{{
				directive.required
					? "Marked required — the run will fail."
					: "The model will be told it is unavailable."
			}}
		</p>
	</div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
	directive: { type: Object, required: true },
	/** One entry from resolve_workflow_tools, or null when not resolved yet. */
	resolution: { type: Object, default: null },
	server: { type: String, default: "" },
	readonly: { type: Boolean, default: false },
});

defineEmits(["remove", "toggle-priority", "toggle-required"]);

const priority = computed(() => props.directive.priority || "primary");

const badge = computed(() => {
	const status = props.resolution?.status;
	if (status === "resolved") {
		return {
			tone: "ok",
			label: "Available",
			title: props.resolution.prefixed_name || "Resolved against a connected MCP server",
		};
	}
	if (status === "missing") {
		return { tone: "bad", label: "Missing", title: "No connected server provides this tool" };
	}
	return { tone: "unknown", label: "Unchecked", title: "Availability not checked yet" };
});
</script>

<style scoped>
.tool-card {
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	overflow: hidden;
	transition: border-color 0.15s ease;
}

.tool-card.missing {
	border-color: var(--ql-danger);
}

.tool-card-header {
	display: flex;
	align-items: center;
	gap: 0.375rem;
	padding: 0.5rem 0.5rem 0.25rem;
}

.tool-card-name {
	flex: 1;
	font-size: 0.8125rem;
	font-weight: 600;
	color: var(--ql-text);
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
	min-width: 0;
}

.resolution-badge {
	display: inline-flex;
	align-items: center;
	gap: 0.25rem;
	flex-shrink: 0;
	padding: 0.0625rem 0.375rem;
	font-size: 0.625rem;
	font-weight: 600;
	border-radius: 9999px;
	border: 1px solid var(--ql-border);
	color: var(--ql-text-muted);
}

.badge-dot {
	width: 5px;
	height: 5px;
	border-radius: 50%;
	background: currentColor;
}

.resolution-badge.ok {
	color: var(--ql-success);
	border-color: color-mix(in srgb, var(--ql-success) 40%, transparent);
}

.resolution-badge.bad {
	color: var(--ql-danger);
	border-color: color-mix(in srgb, var(--ql-danger) 40%, transparent);
}

.priority-pill {
	flex-shrink: 0;
	padding: 0.0625rem 0.375rem;
	font-size: 0.625rem;
	font-weight: 700;
	border: none;
	border-radius: 0.25rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.priority-pill:disabled {
	cursor: default;
	opacity: 0.7;
}

.priority-pill.primary {
	color: white;
	background: var(--ql-accent);
}

.priority-pill.secondary {
	color: var(--ql-text-muted);
	background: var(--ql-subtle);
	border: 1px solid var(--ql-border);
}

.priority-pill:hover:not(:disabled) {
	opacity: 0.85;
}

.remove-tool-btn {
	flex-shrink: 0;
	display: flex;
	align-items: center;
	justify-content: center;
	width: 1.25rem;
	height: 1.25rem;
	background: transparent;
	border: none;
	color: var(--ql-text-muted);
	border-radius: 0.25rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.remove-tool-btn:hover {
	background: color-mix(in srgb, var(--ql-danger) 12%, transparent);
	color: var(--ql-danger);
}

.tool-card-subtitle {
	display: flex;
	align-items: baseline;
	gap: 0.375rem;
	padding: 0 0.5rem 0.25rem;
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	line-height: 1.3;
}

.tool-server-badge {
	flex-shrink: 0;
	font-weight: 600;
}

.tool-card-desc {
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
	min-width: 0;
}

.tool-required {
	display: flex;
	align-items: center;
	gap: 0.375rem;
	padding: 0 0.5rem 0.5rem;
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	cursor: pointer;
}

.tool-required input {
	accent-color: var(--ql-accent);
}

.tool-card-warning {
	margin: 0;
	padding: 0.375rem 0.5rem;
	font-size: 0.6875rem;
	line-height: 1.4;
	color: var(--ql-danger);
	background: color-mix(in srgb, var(--ql-danger) 8%, transparent);
	border-top: 1px solid color-mix(in srgb, var(--ql-danger) 25%, transparent);
}
</style>
