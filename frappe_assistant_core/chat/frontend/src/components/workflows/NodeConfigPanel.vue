<template>
	<aside class="config-panel">
		<ConfigPanelHeader
			:label="node.data?.label || ''"
			:color="nodeColor"
			:readonly="readonly"
			@rename="(label) => emit('update', node.id, { label })"
			@delete="emit('delete', node.id)"
			@close="emit('close')"
		/>

		<!-- Body — type-specific config -->
		<div class="panel-body" role="form">
			<!-- Agent Config (extracted) -->
			<AgentConfig
				v-if="node.type === 'agent'"
				:key="node.id"
				:config="config"
				:node-id="node.id"
				:models="models"
				:models-error="modelsError || ''"
				:all-tools="allTools"
				:tools-result="toolsResult"
				:is-loading-tools="isLoadingTools"
				:variables="variables"
				:runtime-user-label="userLabel"
				:runtime-user="runtimeUser"
				:readonly="readonly"
				@update="handleAgentUpdate"
				@reload-tools="reloadTools"
			/>

			<ToolNodeConfig
				v-else-if="node.type === 'tool'"
				:key="node.id"
				:config="config"
				:all-tools="allTools"
				:is-loading-tools="isLoadingTools"
				:runtime-user-label="userLabel"
				:readonly="readonly"
				@update="handleAgentUpdate"
			/>

			<LoopNodeConfig
				v-else-if="node.type === 'loop'"
				:key="node.id"
				:config="config"
				:node-id="node.id"
				:models="models"
				:models-error="modelsError || ''"
				:all-tools="allTools"
				:tools-result="toolsResult"
				:is-loading-tools="isLoadingTools"
				:variables="variables"
				:runtime-user-label="userLabel"
				:runtime-user="runtimeUser"
				:readonly="readonly"
				@update="handleAgentUpdate"
				@reload-tools="reloadTools"
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
				<label class="config-label">{{ __("Node ID") }}</label>
				<code class="id-value">{{ node.id }}</code>
			</div>
		</div>
	</aside>
</template>

<script setup>
import { reactive, watch, onMounted, onBeforeUnmount, computed } from "vue";
import { storeToRefs } from "pinia";
import { useUserStore } from "@/stores/userStore";
import { useWorkflowStore } from "@/stores/workflowStore";
import { __ } from "@/utils/i18n";
import { NODE_TYPES } from "./graphUtils";
import AgentConfig from "./AgentConfig.vue";
import NodeRunSection from "./NodeRunSection.vue";
import SimpleNodeConfig from "./config/SimpleNodeConfig.vue";
import ToolNodeConfig from "./config/ToolNodeConfig.vue";
import LoopNodeConfig from "./config/LoopNodeConfig.vue";
import ConfigPanelHeader from "./config/ConfigPanelHeader.vue";

const TOOLS_RELOAD_DELAY_MS = 400;

const props = defineProps({
	node: { type: Object, required: true },
	/** Workflow-level global_settings.variables — feeds the prompt preview. */
	variables: { type: Object, default: () => ({}) },
	/** The workflow's default_user_id, i.e. whose MCP tools the run uses. */
	runtimeUserLabel: { type: String, default: "" },
	readonly: { type: Boolean, default: false },
});

const emit = defineEmits(["update", "delete", "close", "request-save"]);

const userStore = useUserStore();
const { user, isAdmin } = storeToRefs(userStore);
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

const config = reactive({});

const userLabel = computed(() => props.runtimeUserLabel || __("this agent's user"));
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
		tool: "#0F6E5C",
		loop: "#8A857C",
		"workflow-output": "#8A857C",
	};
	return byType[props.node.type] || "#64748b";
});

// Sync node data into local state when node changes
watch(
	() => props.node,
	(n) => {
		Object.keys(config).forEach((k) => delete config[k]);
		Object.assign(config, JSON.parse(JSON.stringify(n.data?.config || {})));
	},
	{ immediate: true, deep: true }
);

// Whose MCP tools this node sees. Only a System Manager may name another user;
// the backend rejects it for anyone else, so a non-admin sends nothing and
// gets their own inventory.
const runtimeUser = computed(() => {
	if (!isAdmin.value) return null;
	return config.user_id || currentWorkflow.value?.default_user_id || null;
});

let toolsTimer = null;
watch(
	() => props.node.id,
	() => {
		// A different node is a deliberate switch, not typing: load without waiting.
		clearTimeout(toolsTimer);
		workflowStore.loadTools(runtimeUser.value);
	},
	{ flush: "post" }
);
watch(runtimeUser, (value) => {
	// The override box fires per keystroke; wait for the typing to settle.
	clearTimeout(toolsTimer);
	toolsTimer = setTimeout(() => workflowStore.loadTools(value), TOOLS_RELOAD_DELAY_MS);
});

onMounted(() => {
	if (models.value.length === 0) workflowStore.loadModels();
	workflowStore.loadTools(runtimeUser.value);
});

onBeforeUnmount(() => clearTimeout(toolsTimer));

function reloadTools() {
	workflowStore.loadTools(runtimeUser.value, { force: true });
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
