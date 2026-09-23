<template>
	<div
		ref="rootEl"
		class="canvas-area"
		@drop="$emit('drop', $event)"
		@dragover.prevent
		@dragenter.prevent
	>
		<BuilderNotices
			:read-only="!canEdit"
			:save-error="saveError"
			:action-error="actionError"
			:validation-errors="validationErrors"
			@retry-save="$emit('retry-save')"
			@dismiss-error="$emit('dismiss-error')"
			@dismiss-action-error="$emit('dismiss-action-error')"
		/>

		<div v-if="isLoading" class="canvas-loading">
			<div class="loading-spinner"></div>
			<p>Loading agent…</p>
		</div>

		<div v-else-if="loadError" class="canvas-error">
			<p>{{ loadError }}</p>
			<button class="retry-btn" @click="$emit('retry-load')">Retry</button>
		</div>

		<VueFlow
			v-else
			:nodes="nodes"
			:edges="edges"
			:node-types="nodeComponents"
			:default-viewport="{ zoom: 1, x: 0, y: 0 }"
			:snap-to-grid="true"
			:snap-grid="[16, 16]"
			:min-zoom="0.25"
			:max-zoom="2"
			:fit-view-on-init="true"
			:delete-key-code="canEdit ? ['Backspace', 'Delete'] : null"
			:nodes-draggable="canEdit"
			:nodes-connectable="canEdit"
			:edges-updatable="canEdit"
			:is-valid-connection="isValidConnection"
			@nodes-change="$emit('nodes-change', $event)"
			@edges-change="$emit('edges-change', $event)"
			@connect="$emit('connect', $event)"
			@node-click="$emit('node-click', $event)"
			@pane-click="$emit('pane-click')"
			class="workflow-canvas"
		>
			<Controls :show-fit-view="true" :show-interactive="false" />
			<MiniMap
				:node-color="minimapNodeColor"
				:pannable="true"
				:zoomable="true"
				:mask-color="minimapMaskColor"
				:mask-stroke-color="'var(--ql-accent)'"
				:mask-stroke-width="1"
			/>
		</VueFlow>
	</div>
</template>

<script setup>
import { ref, markRaw } from "vue";
import { VueFlow } from "@vue-flow/core";
import { Controls } from "@vue-flow/controls";
import { MiniMap } from "@vue-flow/minimap";

import { useThemeStore } from "@/stores/themeStore";
import { useWorkflowMinimap } from "@/composables/useWorkflowMinimap";
import BuilderNotices from "@/components/workflows/BuilderNotices.vue";

import InputNode from "@/components/workflows/nodes/InputNode.vue";
import OutputNode from "@/components/workflows/nodes/OutputNode.vue";
import AgentNode from "@/components/workflows/nodes/AgentNode.vue";
import ConditionNode from "@/components/workflows/nodes/ConditionNode.vue";
import TransformNode from "@/components/workflows/nodes/TransformNode.vue";

// Custom node type registration (markRaw required by Vue Flow)
const nodeComponents = {
	"workflow-input": markRaw(InputNode),
	"workflow-output": markRaw(OutputNode),
	agent: markRaw(AgentNode),
	condition: markRaw(ConditionNode),
	transform: markRaw(TransformNode),
};

defineProps({
	nodes: { type: Array, default: () => [] },
	edges: { type: Array, default: () => [] },
	canEdit: { type: Boolean, default: false },
	isLoading: { type: Boolean, default: false },
	loadError: { type: String, default: "" },
	saveError: { type: String, default: "" },
	actionError: { type: String, default: "" },
	validationErrors: { type: Array, default: () => [] },
	isValidConnection: { type: Function, default: null },
});

defineEmits([
	"nodes-change",
	"edges-change",
	"connect",
	"node-click",
	"pane-click",
	"drop",
	"retry-load",
	"retry-save",
	"dismiss-error",
	"dismiss-action-error",
]);

// The drop handler resolves the pane from the event's currentTarget, so the
// builder needs this element — both for that and to place palette clicks.
const rootEl = ref(null);
defineExpose({ rootEl });

const { minimapNodeColor, minimapMaskColor } = useWorkflowMinimap(useThemeStore());
</script>

<style scoped>
.canvas-area {
	flex: 1;
	position: relative;
	min-width: 0;
}

/* Loading & error states */
.canvas-loading,
.canvas-error {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	height: 100%;
	color: var(--ql-text-muted);
	gap: 0.5rem;
}

.loading-spinner {
	width: 2rem;
	height: 2rem;
	border: 2px solid var(--ql-border);
	border-top-color: var(--ql-accent);
	border-radius: 50%;
	animation: spin 0.8s linear infinite;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

.retry-btn {
	padding: 0.375rem 0.75rem;
	font-size: 0.8125rem;
	color: var(--ql-accent);
	background: transparent;
	border: 1px solid var(--ql-accent);
	border-radius: 0.375rem;
	cursor: pointer;
	margin-top: 0.5rem;
}

.retry-btn:hover {
	background: var(--ql-accent-soft);
}

.workflow-canvas {
	width: 100%;
	height: 100%;
}
</style>

<style>
/* Required Vue Flow base styles (no theme-default.css — our custom nodes provide all styling) */
@import "@vue-flow/core/dist/style.css";
@import "@vue-flow/controls/dist/style.css";
@import "@vue-flow/minimap/dist/style.css";
/* Canvas theming + live run-state classes (global by necessity — they cross
   into Vue Flow's own markup and into the scoped custom node components). */
@import "@/styles/workflow-canvas.css";
</style>
