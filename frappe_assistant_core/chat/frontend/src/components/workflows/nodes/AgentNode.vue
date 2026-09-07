<template>
	<div class="workflow-node agent-node">
		<Handle type="target" :position="Position.Left" />
		<div class="node-header">
			<div class="node-icon" style="color: var(--ql-accent)">
				<svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
					/>
				</svg>
			</div>
			<span class="node-label">{{ data.label }}</span>
			<span class="node-type-badge agent-badge">AI</span>
		</div>
		<div v-if="data.config?.system_prompt" class="node-preview">
			{{ truncate(data.config.system_prompt, 50) }}
		</div>
		<div class="node-meta">
			<span v-if="data.config?.model_id" class="meta-pill">{{
				shortModel(data.config.model_id)
			}}</span>
			<span v-if="toolCount > 0" class="meta-pill"
				>{{ toolCount }} tool{{ toolCount > 1 ? "s" : "" }}</span
			>
			<span v-if="data.config?.use_memory" class="meta-pill" title="Team instructions + memories"
				>memory</span
			>
		</div>
		<Handle type="source" :position="Position.Right" />
	</div>
</template>

<script setup>
import { computed } from "vue";
import { Handle, Position } from "@vue-flow/core";

const props = defineProps({
	data: { type: Object, required: true },
});

// Tools are directives; mcp_servers is a server list and was never the count.
const toolCount = computed(() => props.data.config?.tool_directives?.length || 0);

function truncate(text, len) {
	if (!text) return "";
	return text.length > len ? text.slice(0, len) + "..." : text;
}

function shortModel(modelId) {
	if (!modelId) return "";
	// "claude-sonnet-4-5-20250929" → "sonnet-4.5"
	const parts = modelId.split("-");
	if (parts.length >= 3) return parts.slice(1, 3).join("-");
	return modelId.slice(0, 12);
}
</script>

<style scoped>
.workflow-node {
	background: var(--ql-surface);
	border: 2px solid var(--ql-border);
	border-radius: 0.5rem;
	padding: 0.625rem 0.75rem;
	min-width: 180px;
	max-width: 240px;
	transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.workflow-node:hover {
	border-color: var(--ql-accent);
}

.node-header {
	display: flex;
	align-items: center;
	gap: 0.5rem;
}

.node-icon {
	flex-shrink: 0;
	display: flex;
}

.node-label {
	flex: 1;
	font-size: 0.8125rem;
	font-weight: 600;
	color: var(--ql-text);
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.node-type-badge {
	flex-shrink: 0;
	font-size: 0.625rem;
	font-weight: 700;
	padding: 0.0625rem 0.375rem;
	border-radius: 0.25rem;
}

.agent-badge {
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
}

.node-preview {
	margin-top: 0.375rem;
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	display: -webkit-box;
	-webkit-line-clamp: 2;
	-webkit-box-orient: vertical;
	overflow: hidden;
	line-height: 1.4;
}

.node-meta {
	display: flex;
	gap: 0.25rem;
	margin-top: 0.375rem;
	flex-wrap: wrap;
}

.meta-pill {
	font-size: 0.625rem;
	font-weight: 500;
	padding: 0.0625rem 0.375rem;
	border-radius: 0.25rem;
	background: var(--ql-subtle);
	color: var(--ql-text-muted);
}
</style>
