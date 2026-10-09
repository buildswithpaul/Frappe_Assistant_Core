<template>
	<div class="builder-layout">
		<!-- Mobile gate -->
		<MobileGate v-if="isMobile" @back="router.push({ name: 'agents' })" />

		<template v-else>
			<!-- Toolbar -->
			<WorkflowToolbar
				:name="workflowDisplayName"
				:status="currentWorkflow?.status || 'Draft'"
				:is-dirty="isDirty"
				:is-saving="isSaving"
				:is-running="isRunning"
				:can-run="canRun"
				:run-block-reason="runBlockReason"
				:show-runs="showRunsPanel"
				:show-audit="showAuditPanel"
				:last-saved="hasSaved"
				:has-variables="hasVariables"
				:setup-todo="setup.todoCount.value"
				@back="handleBack"
				@save="save"
				@run="requestRun"
				@setup="showSetup = !showSetup"
				@toggle-runs="onToggleRuns"
				@toggle-audit="onToggleAudit"
				@toggle-status="requestToggleStatus"
				@rename="rename"
				@variables="showVariablesModal = true"
				@share-template="showShareModal = true"
			/>

			<!-- Canvas area -->
			<div class="builder-body">
				<NodePalette
					v-if="canEdit"
					:collapsed="paletteCollapsed"
					@toggle="paletteCollapsed = !paletteCollapsed"
					@add="addNodeOfType"
				/>

				<WorkflowCanvas
					ref="canvasRef"
					:nodes="nodes"
					:edges="edges"
					:can-edit="canEdit"
					:is-loading="isLoading"
					:load-error="loadError || ''"
					:save-error="saveError || ''"
					:action-error="actionError || ''"
					:validation-errors="visibleErrors"
					:is-valid-connection="isValidConnection"
					@nodes-change="onNodesChange"
					@edges-change="onEdgesChange"
					@connect="onConnect"
					@node-click="onNodeClick"
					@pane-click="onPaneClick"
					@drop="onCanvasDrop"
					@retry-load="loadCurrentWorkflow"
					@retry-save="save"
					@dismiss-error="saveError = null"
					@dismiss-action-error="actionError = null"
				/>

				<BuilderRightRail
					:selected-node="selectedNode"
					:variables="globalSettings?.variables || {}"
					:runtime-user-label="runtimeUserLabel"
					:readonly="!canEdit"
					:show-runs="showRunsPanel"
					:show-audit="showAuditPanel"
					:workflow-id="workflowId"
					@node-update="handleNodeUpdate"
					@node-delete="handleDeleteNode"
					@close-config="selectedNode = null"
					@request-save="save"
					@close-runs="showRunsPanel = false"
					@close-audit="showAuditPanel = false"
				/>
			</div>

			<!-- Status Bar -->
			<WorkflowStatusBar
				:node-count="nodes.length"
				:edge-count="edges.length"
				:validation-message="validationMessage"
				:validation-class="validationClass"
				:save-error="saveError"
				:is-dirty="isDirty"
				:has-saved="hasSaved"
			/>

			<!-- Modals (run input, schedule, variables, share template, triggers, setup, activation) -->
			<WorkflowBuilderModals
				v-model:show-run="showRunModal"
				v-model:show-schedule="showScheduleModal"
				v-model:show-variables="showVariablesModal"
				v-model:show-share="showShareModal"
				v-model:show-triggers="showTriggersModal"
				v-model:show-setup="showSetup"
				:is-running="isRunning"
				:schedule-config="scheduleConfig"
				:is-setting-schedule="isSettingSchedule"
				:variables="globalSettings?.variables || {}"
				:workflow-id="workflowId"
				:workflow-display-name="workflowDisplayName"
				:setup-items="setup.items.value"
				:setup-busy="setup.isRefreshing.value"
				:pending-activation="pendingActivation"
				:activation-warnings="preflight.warnings.value"
				@setup-action="(key) => panels.onSetupAction(key, setup)"
				@activation-confirm="confirmActivation"
				@activation-cancel="cancelActivation"
				@run-confirm="confirmRun"
				@schedule-save="saveSchedule"
				@variables-save="onVariablesSave"
			/>

			<WorkflowSettingsDrawer
				v-model="showSettingsDrawer"
				:workflow="currentWorkflow"
				:models="availableModels"
				:current-user="user || ''"
				:is-saving="isSaving"
				:error="settingsError || ''"
				@save="onSettingsSave"
			/>
		</template>
	</div>
</template>

<script setup>
import { ref, computed, nextTick, onBeforeUnmount, onMounted } from "vue";
import { useRouter, useRoute } from "vue-router";
import { storeToRefs } from "pinia";
import { useVueFlow } from "@vue-flow/core";

import { useWorkflowStore } from "@/stores/workflowStore";
import { useUserStore } from "@/stores/userStore";
import WorkflowToolbar from "@/components/workflows/WorkflowToolbar.vue";
import WorkflowStatusBar from "@/components/workflows/WorkflowStatusBar.vue";
import WorkflowBuilderModals from "@/components/workflows/WorkflowBuilderModals.vue";
import WorkflowSettingsDrawer from "@/components/workflows/WorkflowSettingsDrawer.vue";
import MobileGate from "@/components/workflows/MobileGate.vue";
import NodePalette from "@/components/workflows/NodePalette.vue";
import WorkflowCanvas from "@/components/workflows/builder/WorkflowCanvas.vue";
import BuilderRightRail from "@/components/workflows/builder/BuilderRightRail.vue";
import { useWorkflowRealtime } from "@/composables/useWorkflowRealtime";
import { useIsMobile } from "@/composables/useIsMobile";
import { useUnsavedGuard } from "@/composables/useUnsavedGuard";
import { useWorkflowLoader } from "@/composables/useWorkflowLoader";
import { useWorkflowGraphActions } from "@/composables/useWorkflowGraphActions";
import { useBuilderGraph } from "@/composables/useBuilderGraph";
import { useBuilderAutosave } from "@/composables/useBuilderAutosave";
import { useRunNodeStatus } from "@/composables/useRunNodeStatus";
import { useGraphValidation } from "@/composables/useGraphValidation";
import { useWorkflowActions } from "@/composables/useWorkflowActions";
import { useWorkflowExecution } from "@/composables/useWorkflowExecution";
import { useBuilderShortcuts } from "@/composables/useBuilderShortcuts";
import { useBuilderPanels } from "@/composables/useBuilderPanels";
import { useBuilderSetup } from "@/composables/useBuilderSetup";
import { vueFlowToGraphJson } from "@/components/workflows/graphUtils";
import { __ } from "@/utils/i18n";

const router = useRouter();
const route = useRoute();
const workflowStore = useWorkflowStore();
const userStore = useUserStore();
const { currentWorkflow, isDirty, isSaving, isRunning, currentRun, availableModels } =
	storeToRefs(workflowStore);
const { user, isAdmin } = storeToRefs(userStore);

const { project, fitView } = useVueFlow();

// Canvas state
const nodes = ref([]);
const edges = ref([]);
const globalSettings = ref({});
const canvasRef = ref(null);
const canvasAreaRef = computed(() => canvasRef.value?.rootEl || null);

// UI state
const selectedNode = ref(null);
const paletteCollapsed = ref(false);
const panels = useBuilderPanels();
const {
	showRunsPanel,
	showAuditPanel,
	showScheduleModal,
	showVariablesModal,
	showShareModal,
	showTriggersModal,
	showSettingsDrawer,
	showSetup,
	onToggleRuns,
	onToggleAudit,
} = panels;

const scheduleConfig = ref({ cron: "", timezone: "UTC", defaultInput: "", enabled: false });

// Every mutation is a System Manager action server-side; a non-admin is a
// viewer, so the canvas is inert rather than autosaving into a wall of 403s.
const canEdit = computed(() => isAdmin.value);

const hasVariables = computed(() => {
	const vars = globalSettings.value?.variables;
	return vars && Object.keys(vars).length > 0;
});

const workflowId = computed(() => route.params.id);
const workflowDisplayName = computed(
	() => currentWorkflow.value?.workflow_name || workflowId.value || __("Untitled"),
);
const runtimeUserLabel = computed(
	() => currentWorkflow.value?.default_user_id || __("no user (tools unavailable)"),
);

function currentGraphJson() {
	return vueFlowToGraphJson(nodes.value, edges.value, globalSettings.value);
}

useWorkflowRealtime(workflowId);
const { isMobile } = useIsMobile();
useUnsavedGuard(isDirty);

useRunNodeStatus(currentRun, isRunning, { nodes, edges });

const {
	validationMessage,
	validationClass,
	visibleErrors,
	canRun,
	runBlockReason,
	checkLocally,
	checkBeforeRun,
	checkOnServer,
} = useGraphValidation({ workflowStore, nodes, edges, toGraphJson: currentGraphJson });

const { hasSaved, saveError, scheduleAutoSave, save, saveBeforeLeave, resetHistory, undo, redo } =
	useBuilderAutosave({
		workflowStore,
		workflowId,
		canEdit,
		nodes,
		edges,
		globalSettings,
		selectedNode,
		toGraphJson: currentGraphJson,
		checkLocally,
		checkOnServer,
	});

const { isLoading, loadError, loadCurrentWorkflow, wasRelaidOut } = useWorkflowLoader({
	workflowStore,
	workflowId,
	nodes,
	edges,
	globalSettings,
	hasSaved,
	scheduleConfig,
});

const {
	onNodesChange,
	onEdgesChange,
	onConnect,
	isValidConnection,
	onNodeClick,
	onPaneClick,
	addNodeOfType,
	duplicateSelectedNode,
	openFocusedNodeConfig,
} = useBuilderGraph({
	nodes,
	edges,
	selectedNode,
	canEdit,
	scheduleAutoSave,
	project,
	canvasAreaRef,
});

const { onDrop, handleNodeUpdate, handleDeleteNode } = useWorkflowGraphActions({
	nodes,
	edges,
	selectedNode,
	scheduleAutoSave,
	project,
});

const { preflight, setup } = useBuilderSetup({
	workflowId,
	workflowDisplayName,
	currentWorkflow,
	scheduleConfig,
	nodes,
	isAdmin,
	showSetup,
});

const {
	settingsError,
	requestToggleStatus,
	pendingActivation,
	confirmActivation,
	cancelActivation,
	rename,
	saveSettings,
} = useWorkflowActions({
	workflowStore,
	workflowId,
	currentWorkflow,
	canEdit,
	isDirty,
	toGraphJson: currentGraphJson,
	hasSaved,
	saveError,
	preflight,
});

const { actionError, isSettingSchedule, showRunModal, requestRun, confirmRun, saveSchedule } =
	useWorkflowExecution({
		workflowStore,
		workflowId,
		canEdit,
		isDirty,
		nodes,
		save,
		checkBeforeRun,
		scheduleConfig,
		showRunsPanel,
		showScheduleModal,
	});

useBuilderShortcuts({
	isEnabled: () => !isMobile.value,
	onSave: save,
	onUndo: undo,
	onRedo: redo,
	onDuplicate: duplicateSelectedNode,
	onFitView: () => fitView({ padding: 0.2 }),
	onEscape: () => {
		if (showSettingsDrawer.value) showSettingsDrawer.value = false;
		else selectedNode.value = null;
	},
	onOpenConfig: openFocusedNodeConfig,
});

onMounted(async () => {
	await loadCurrentWorkflow();
	resetHistory();
	if (wasRelaidOut.value) {
		await nextTick();
		fitView({ padding: 0.2 });
		if (canEdit.value) scheduleAutoSave();
	}
	if (canEdit.value) setup.refresh();
});

onBeforeUnmount(() => workflowStore.clearCurrentWorkflow());

function onCanvasDrop(event) {
	if (!canEdit.value) return;
	onDrop(event);
}

async function onSettingsSave(fields) {
	if (await saveSettings(fields)) showSettingsDrawer.value = false;
}

function onVariablesSave(vars) {
	if (!globalSettings.value) globalSettings.value = {};
	globalSettings.value.variables = vars;
	showVariablesModal.value = false;
	scheduleAutoSave();
}

async function handleBack() {
	// A failed save keeps the author here with the save banner up.
	if (await saveBeforeLeave()) router.push({ name: "agents" });
}
</script>

<style scoped>
.builder-layout {
	display: flex;
	flex-direction: column;
	height: 100%;
	min-height: 0;
	background: var(--ql-bg);
	overflow: hidden;
}

.builder-body {
	flex: 1;
	display: flex;
	overflow: hidden;
	min-height: 0;
}
</style>
