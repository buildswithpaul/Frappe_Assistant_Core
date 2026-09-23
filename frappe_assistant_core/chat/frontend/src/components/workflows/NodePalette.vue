<template>
	<aside class="node-palette" :class="{ collapsed }">
		<div class="palette-header">
			<span v-if="!collapsed" class="palette-title">Nodes</span>
			<button
				@click="$emit('toggle')"
				class="collapse-btn"
				:title="collapsed ? 'Expand palette' : 'Collapse palette'"
				:aria-label="collapsed ? 'Expand node palette' : 'Collapse node palette'"
			>
				<svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						:d="collapsed ? 'M9 5l7 7-7 7' : 'M15 19l-7-7 7-7'"
					/>
				</svg>
			</button>
		</div>

		<div v-if="!collapsed" class="palette-nodes">
			<button
				v-for="nt in nodeTypes"
				:key="nt.type"
				type="button"
				class="palette-item"
				:title="`Add ${nt.label}`"
				draggable="true"
				@dragstart="onDragStart($event, nt.type)"
				@click="$emit('add', nt.type)"
			>
				<div class="palette-icon" :style="{ color: nt.color }">
					<svg
						width="16"
						height="16"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							:d="nt.iconPath"
						/>
					</svg>
				</div>
				<div class="palette-info">
					<span class="palette-label">{{ nt.label }}</span>
					<span class="palette-desc">{{ nt.description }}</span>
				</div>
			</button>
		</div>

		<div v-else class="palette-icons-only">
			<button
				v-for="nt in nodeTypes"
				:key="nt.type"
				type="button"
				class="palette-icon-item"
				draggable="true"
				@dragstart="onDragStart($event, nt.type)"
				@click="$emit('add', nt.type)"
				:title="`Add ${nt.label}`"
			>
				<svg
					width="18"
					height="18"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					:style="{ color: nt.color }"
				>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						:d="nt.iconPath"
					/>
				</svg>
			</button>
		</div>
	</aside>
</template>

<script setup>
import { NODE_TYPES } from "./graphUtils";

defineProps({
	collapsed: { type: Boolean, default: false },
});

// Click-to-add is not a convenience: drag-and-drop never worked on touch.
defineEmits(["toggle", "add"]);

const nodeTypes = NODE_TYPES;

function onDragStart(event, type) {
	event.dataTransfer.setData("application/workflow-node-type", type);
	event.dataTransfer.effectAllowed = "move";
}
</script>

<style scoped>
.node-palette {
	width: 200px;
	background: var(--ql-surface);
	border-right: 1px solid var(--ql-border);
	display: flex;
	flex-direction: column;
	flex-shrink: 0;
	overflow: hidden;
	transition: width 0.2s ease;
}

.node-palette.collapsed {
	width: 48px;
}

.palette-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 0.75rem;
	border-bottom: 1px solid var(--ql-border);
}

.palette-title {
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.05em;
}

.collapse-btn {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 24px;
	height: 24px;
	background: transparent;
	border: none;
	color: var(--ql-text-muted);
	border-radius: 0.25rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.collapse-btn:hover {
	background: var(--ql-subtle);
	color: var(--ql-text);
}

.palette-nodes {
	flex: 1;
	overflow-y: auto;
	padding: 0.5rem;
	display: flex;
	flex-direction: column;
	gap: 0.25rem;
}

.palette-item {
	display: flex;
	align-items: center;
	gap: 0.625rem;
	width: 100%;
	padding: 0.5rem 0.625rem;
	text-align: left;
	background: transparent;
	border: none;
	border-radius: 0.375rem;
	cursor: grab;
	transition: background 0.15s ease;
	user-select: none;
}

.palette-item:focus-visible,
.palette-icon-item:focus-visible {
	outline: 2px solid var(--ql-accent);
	outline-offset: -2px;
}

.palette-item:hover {
	background: var(--ql-subtle);
}

.palette-item:active {
	cursor: grabbing;
}

.palette-icon {
	flex-shrink: 0;
	display: flex;
}

.palette-info {
	display: flex;
	flex-direction: column;
	min-width: 0;
}

.palette-label {
	font-size: 0.8125rem;
	font-weight: 600;
	color: var(--ql-text);
	line-height: 1.2;
}

.palette-desc {
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	line-height: 1.2;
	margin-top: 0.125rem;
}

/* Collapsed mode — icons only */
.palette-icons-only {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 0.25rem;
	padding: 0.5rem 0;
}

.palette-icon-item {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 36px;
	height: 36px;
	background: transparent;
	border: none;
	border-radius: 0.375rem;
	cursor: grab;
	transition: background 0.15s ease;
}

.palette-icon-item:hover {
	background: var(--ql-subtle);
}

.palette-icon-item:active {
	cursor: grabbing;
}
</style>
