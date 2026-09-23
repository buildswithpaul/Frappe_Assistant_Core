<template>
	<Teleport to="body">
		<div
			v-if="modelValue"
			class="modal-overlay"
			role="dialog"
			aria-modal="true"
			aria-label="Agent triggers"
			@click.self="close"
		>
			<div class="modal-content wide">
				<div class="modal-header">
					<h2 class="modal-title">Event Triggers</h2>
					<p class="modal-subtitle">
						Fire this agent when a document event happens on your Frappe site.
					</p>
				</div>

				<div v-if="loading" class="state-block">Loading triggers…</div>

				<div v-else-if="!showEditor && !showLog">
					<div class="triggers-toolbar">
						<button class="action-btn primary" @click="openNewEditor">
							+ Add Trigger
						</button>
					</div>

					<div v-if="triggers.length === 0" class="empty-state">
						No triggers yet. Create one to run this agent automatically when a
						document is inserted, updated, submitted, cancelled, or deleted.
					</div>

					<div v-else class="triggers-list">
						<TriggerCard
							v-for="t in triggers"
							:key="t.name"
							:trigger="t"
							@edit="editTrigger"
							@delete="deleteTrigger"
							@toggle="toggleTrigger"
							@view-log="viewLog"
						/>
					</div>
				</div>

				<TriggerEditor
					v-else-if="showEditor"
					:workflow-name="workflowDisplayName"
					:workflow-id="workflowId"
					:workflow-display-name="workflowDisplayName"
					:existing="editorTarget"
					@save="saveTrigger"
					@cancel="closeEditor"
				/>

				<TriggerFireLog
					v-else-if="showLog"
					:trigger-name="logTarget?.name"
					:trigger-title="logTarget?.title"
					@back="closeLog"
				/>

				<div v-if="!showEditor && !showLog" class="modal-actions">
					<button class="action-btn" @click="close">Close</button>
				</div>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
import { ref, watch } from "vue";
import api from "@/api/client";
import TriggerCard from "./TriggerCard.vue";
import TriggerEditor from "./TriggerEditor.vue";
import TriggerFireLog from "./TriggerFireLog.vue";
import { logger } from "@/utils/logger";

const props = defineProps({
	modelValue: { type: Boolean, required: true },
	/** AR Workflow docname (WF-#####) — the authoritative trigger binding. */
	workflowId: { type: String, required: true },
	workflowDisplayName: { type: String, default: "" },
});

const emit = defineEmits(["update:modelValue"]);

const loading = ref(false);
const triggers = ref([]);
const showEditor = ref(false);
const editorTarget = ref(null);
const showLog = ref(false);
const logTarget = ref(null);

watch(
	() => props.modelValue,
	(v) => {
		if (v) {
			refresh();
			showEditor.value = false;
			showLog.value = false;
		}
	}
);

async function refresh() {
	loading.value = true;
	try {
		const res = await api.workflows.triggers.list(
			props.workflowDisplayName,
			props.workflowId
		);
		triggers.value = res?.triggers || [];
	} catch (err) {
		logger.error("Failed to load triggers", err);
		triggers.value = [];
	} finally {
		loading.value = false;
	}
}

function openNewEditor() {
	editorTarget.value = null;
	showEditor.value = true;
}

function editTrigger(t) {
	editorTarget.value = t;
	showEditor.value = true;
}

async function deleteTrigger(t) {
	if (!confirm(`Delete trigger "${t.title}"?`)) return;
	try {
		await api.workflows.triggers.delete(t.name);
		await refresh();
	} catch (err) {
		alert(`Failed to delete: ${err?.message || err}`);
	}
}

async function toggleTrigger(t) {
	try {
		await api.workflows.triggers.toggle(t.name, !t.enabled);
		await refresh();
	} catch (err) {
		alert(`Failed to toggle: ${err?.message || err}`);
	}
}

function viewLog(t) {
	logTarget.value = t;
	showLog.value = true;
}

function closeLog() {
	showLog.value = false;
	logTarget.value = null;
}

async function saveTrigger(payload) {
	try {
		if (editorTarget.value) {
			await api.workflows.triggers.update(editorTarget.value.name, payload);
		} else {
			// workflow_docname is the binding the dispatcher should resolve;
			// workflow_name stays the display column it has always been.
			await api.workflows.triggers.create({
				...payload,
				workflow_name: props.workflowDisplayName,
				workflow_docname: props.workflowId,
				workflow_display_name: props.workflowDisplayName,
			});
		}
		showEditor.value = false;
		editorTarget.value = null;
		await refresh();
	} catch (err) {
		alert(`Failed to save: ${err?.message || err}`);
	}
}

function closeEditor() {
	showEditor.value = false;
	editorTarget.value = null;
}

function close() {
	emit("update:modelValue", false);
}
</script>

<style scoped>
.modal-overlay {
	position: fixed;
	inset: 0;
	background: rgba(0, 0, 0, 0.5);
	display: flex;
	align-items: center;
	justify-content: center;
	z-index: 1050;
	padding: 1rem;
}
.modal-content {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	color: var(--ql-text);
	border-radius: 0.75rem;
	padding: 1.5rem;
	max-width: 36rem;
	width: 100%;
	max-height: 85vh;
	overflow-y: auto;
	box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}
.modal-content.wide {
	max-width: 48rem;
}
.modal-header {
	margin-bottom: 1rem;
}
.modal-title {
	margin: 0;
	font-size: 1.125rem;
	font-weight: 600;
	color: var(--ql-text);
}
.modal-subtitle {
	margin: 0.25rem 0 0;
	font-size: 0.8125rem;
	color: var(--ql-text-secondary);
}
.triggers-toolbar {
	margin-bottom: 1rem;
	display: flex;
	justify-content: flex-end;
}
.triggers-list {
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
}
.empty-state {
	padding: 1.5rem;
	text-align: center;
	color: var(--ql-text-secondary);
	background: var(--ql-subtle);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	font-size: 0.875rem;
}
.state-block {
	padding: 1.5rem;
	text-align: center;
	color: var(--ql-text-secondary);
}
.modal-actions {
	margin-top: 1.25rem;
	display: flex;
	justify-content: flex-end;
	gap: 0.5rem;
}
.action-btn {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.5rem 0.875rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
	background: var(--ql-subtle);
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
}
.action-btn:hover {
	background-color: var(--ql-border);
}
.action-btn.primary {
	color: white;
	background: var(--ql-accent);
}
.action-btn.primary:hover {
	background: var(--ql-accent-hover);
}
</style>
