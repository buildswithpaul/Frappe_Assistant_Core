<template>
	<aside class="config-panel">
		<!-- Header -->
		<div class="panel-header">
			<div class="header-info">
				<div class="node-type-indicator" :style="{ background: nodeColor }"></div>
				<input
					v-model="editLabel"
					class="label-input"
					:readonly="readonly"
					@blur="updateLabel"
					@keydown.enter="$event.target.blur()"
				/>
			</div>
			<div class="header-actions">
				<button
					v-if="!readonly"
					@click="$emit('delete', node.id)"
					class="header-btn danger"
					title="Delete node"
					aria-label="Delete node"
				>
					<svg
						width="14"
						height="14"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
						/>
					</svg>
				</button>
				<button
					@click="$emit('close')"
					class="header-btn"
					title="Close"
					aria-label="Close panel"
				>
					<svg
						width="14"
						height="14"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M6 18L18 6M6 6l12 12"
						/>
					</svg>
				</button>
			</div>
		</div>

		<!-- Body — type-specific config -->
		<div class="panel-body" role="form">
			<!-- Agent Config (extracted) -->
			<AgentConfig
				v-if="node.type === 'agent'"
				:config="config"
				:node-id="node.id"
				:models="models"
				:models-error="modelsError || ''"
				:all-tools="allTools"
				:tools-result="toolsResult"
				:is-loading-tools="isLoadingTools"
				:variables="variables"
				:runtime-user-label="runtimeUserLabel"
				:readonly="readonly"
				@update="handleAgentUpdate"
				@reload-tools="workflowStore.loadTools()"
			/>

			<!-- Condition / Transform / Input / Output — small, shared shell -->
			<SimpleNodeConfig
				v-else
				:node-type="node.type"
				:config="config"
				:readonly="readonly"
				@update="emitUpdate"
			/>

			<!-- Run Node Section (agent & transform only) -->
			<NodeRunSection
				v-if="canRunNode && !readonly"
				:node-id="node.id"
				:node-type="node.type"
				:is-dirty="isDirty"
				:run-node="executeRunNode"
				:request-save="() => $emit('request-save')"
				:wait-for-save="waitForSave"
			/>

			<!-- Node ID (all types) -->
			<div class="config-section config-id">
				<label class="config-label">Node ID</label>
				<code class="id-value">{{ node.id }}</code>
			</div>
		</div>
	</aside>
</template>

<script setup>
import { ref, reactive, watch, onMounted, computed } from "vue";
import { storeToRefs } from "pinia";
import { useUserStore } from "@/stores/userStore";
import { useWorkflowStore } from "@/stores/workflowStore";
import { NODE_TYPES } from "./graphUtils";
import AgentConfig from "./AgentConfig.vue";
import NodeRunSection from "./NodeRunSection.vue";
import SimpleNodeConfig from "./config/SimpleNodeConfig.vue";

const props = defineProps({
	node: { type: Object, required: true },
	/** Workflow-level global_settings.variables — feeds the prompt preview. */
	variables: { type: Object, default: () => ({}) },
	/** The workflow's default_user_id, i.e. whose MCP tools the run uses. */
	runtimeUserLabel: { type: String, default: "this agent's user" },
	readonly: { type: Boolean, default: false },
});

const emit = defineEmits(["update", "delete", "close", "request-save"]);

const userStore = useUserStore();
const { user } = storeToRefs(userStore);
const workflowStore = useWorkflowStore();
const {
	availableModels: models,
	modelsError,
	availableTools: allTools,
	toolsResult,
	isLoadingTools,
	isDirty,
	currentWorkflow,
} = storeToRefs(workflowStore);

const editLabel = ref("");
const config = reactive({});

const canRunNode = computed(() => ["agent", "transform"].includes(props.node.type));

// Resolve the side-panel dot color from the node type. We map type → resolved
// hex (Quiet Ledger semantics: agent/transform teal, condition gold, input/output
// neutral) rather than reading the CSS-var string off NODE_TYPES, so the lookup
// is independent of how graphUtils expresses its colors.
const nodeColor = computed(() => {
	const meta = NODE_TYPES.find((nt) => nt.type === props.node.type);
	if (meta?.color?.startsWith("#")) return meta.color;
	const byType = {
		"workflow-input": "#8A857C",
		agent: "#0F6E5C",
		condition: "#C9A227",
		transform: "#0F6E5C",
		"workflow-output": "#8A857C",
	};
	return byType[props.node.type] || "#64748b";
});

// Sync node data into local state when node changes
watch(
	() => props.node,
	(n) => {
		editLabel.value = n.data?.label || "";
		Object.keys(config).forEach((k) => delete config[k]);
		Object.assign(config, JSON.parse(JSON.stringify(n.data?.config || {})));
	},
	{ immediate: true, deep: true }
);

onMounted(() => {
	if (models.value.length === 0) workflowStore.loadModels();
	if (allTools.value.length === 0) workflowStore.loadTools();
});

function updateLabel() {
	if (props.readonly) return;
	const trimmed = editLabel.value.trim();
	if (trimmed && trimmed !== props.node.data?.label) {
		emit("update", props.node.id, { label: trimmed });
	}
}

function emitUpdate() {
	if (props.readonly) return;
	emit("update", props.node.id, { config: { ...config } });
}

function handleAgentUpdate(data) {
	// AgentConfig mutates the reactive config directly and emits { config }
	if (props.readonly) return;
	emit("update", props.node.id, data);
}

async function executeRunNode(nodeId, inputText) {
	const wfName = currentWorkflow.value?.name;
	if (!wfName) return;
	return workflowStore.runNode(wfName, nodeId, inputText, user.value);
}

function waitForSave() {
	return new Promise((resolve) => {
		if (!isDirty.value) {
			resolve();
			return;
		}
		const unwatch = watch(isDirty, (val) => {
			if (!val) {
				unwatch();
				resolve();
			}
		});
		setTimeout(() => {
			unwatch();
			resolve();
		}, 10000);
	});
}
</script>

<style scoped>
.config-panel {
	width: 320px;
	background: var(--ql-surface);
	border-left: 1px solid var(--ql-border);
	flex-shrink: 0;
	display: flex;
	flex-direction: column;
	overflow: hidden;
}

.panel-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 0.75rem 1rem;
	border-bottom: 1px solid var(--ql-border);
	gap: 0.5rem;
}

.header-info {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	min-width: 0;
	flex: 1;
}

.node-type-indicator {
	width: 10px;
	height: 10px;
	border-radius: 50%;
	flex-shrink: 0;
}

.label-input {
	flex: 1;
	font-size: 0.875rem;
	font-weight: 600;
	color: var(--ql-text);
	background: transparent;
	border: none;
	border-bottom: 1px solid transparent;
	outline: none;
	padding: 0.125rem 0;
	min-width: 0;
	transition: border-color 0.15s ease;
}

.label-input:focus {
	border-bottom-color: var(--ql-accent);
}

.header-actions {
	display: flex;
	gap: 0.25rem;
	flex-shrink: 0;
}

.header-btn {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 28px;
	height: 28px;
	background: transparent;
	border: none;
	color: var(--ql-text-muted);
	border-radius: 0.25rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.header-btn:hover {
	background: var(--ql-subtle);
	color: var(--ql-text);
}

.header-btn.danger:hover {
	background: rgba(180, 69, 58, 0.1);
	color: var(--ql-danger);
}

.panel-body {
	flex: 1;
	overflow-y: auto;
	padding: 1rem;
}

.config-section {
	margin-bottom: 1rem;
}

.config-label {
	display: block;
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.025em;
	margin-bottom: 0.375rem;
}

.config-label .optional {
	font-weight: 400;
	text-transform: none;
	letter-spacing: 0;
	opacity: 0.7;
}

.config-check-label {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	text-transform: none;
	font-weight: 500;
	cursor: pointer;
}

.config-input {
	width: 100%;
	padding: 0.5rem 0.625rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	outline: none;
	box-sizing: border-box;
	transition: border-color 0.15s ease;
}

.config-input:focus {
	border-color: var(--ql-accent);
}

.config-textarea {
	resize: vertical;
	min-height: 3rem;
	font-family: inherit;
	line-height: 1.5;
}

.config-textarea.mono {
	font-family: "SF Mono", Monaco, "Cascadia Code", monospace;
	font-size: 0.75rem;
	line-height: 1.6;
}

.config-select {
	cursor: pointer;
	appearance: none;
	background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e");
	background-position: right 0.5rem center;
	background-repeat: no-repeat;
	background-size: 1em;
	padding-right: 2rem;
}

.config-hint {
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	margin: 0.25rem 0 0;
	line-height: 1.4;
}

.config-hint code {
	background: var(--ql-subtle);
	padding: 0.0625rem 0.25rem;
	border-radius: 0.1875rem;
	font-size: 0.6875rem;
}

.config-info {
	background: var(--ql-subtle);
	border-radius: 0.375rem;
	padding: 0.625rem 0.75rem;
	margin-top: 0.75rem;
}

.config-info p {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	margin: 0;
	line-height: 1.5;
}

.config-info p + p {
	margin-top: 0.25rem;
}

.config-info strong {
	color: var(--ql-text);
	font-weight: 600;
}

/* Node ID */
.config-id {
	border-top: 1px solid var(--ql-border);
	padding-top: 1rem;
	margin-top: 0.5rem;
}

.id-value {
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	background: var(--ql-subtle);
	padding: 0.25rem 0.5rem;
	border-radius: 0.25rem;
	display: block;
	word-break: break-all;
}
</style>
