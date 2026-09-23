<template>
	<div class="toolbar-left">
		<ToolbarButton title="Back to list" aria-label="Back to agent list" @click="$emit('back')">
			<ToolbarIcon name="back" :size="18" />
		</ToolbarButton>

		<div class="workflow-name-group">
			<input
				v-if="isEditingName"
				ref="nameInputRef"
				v-model="editName"
				class="name-input"
				@blur="saveName"
				@keydown.enter="saveName"
				@keydown.escape="cancelEdit"
			/>
			<h1
				v-else
				class="workflow-name"
				:class="{ editable: canRename }"
				@click="startEditName"
				:title="canRename ? 'Click to rename' : ''"
			>
				{{ name }}
			</h1>
			<span v-if="status" class="status-badge" :class="statusClass">{{ status }}</span>
		</div>
	</div>
</template>

<script setup>
import { ref, computed, nextTick } from "vue";
import ToolbarButton from "./ToolbarButton.vue";
import ToolbarIcon from "./ToolbarIcon.vue";

const props = defineProps({
	name: { type: String, default: "" },
	status: { type: String, default: "" },
	canRename: { type: Boolean, default: false },
});

const emit = defineEmits(["back", "rename"]);

const isEditingName = ref(false);
const editName = ref("");
const nameInputRef = ref(null);

const statusClass = computed(() => {
	const s = props.status?.toLowerCase();
	if (s === "active") return "badge-active";
	if (s === "paused") return "badge-paused";
	if (s === "archived") return "badge-archived";
	return "badge-draft";
});

function startEditName() {
	if (!props.canRename) return;
	editName.value = props.name;
	isEditingName.value = true;
	nextTick(() => nameInputRef.value?.select());
}

function saveName() {
	const trimmed = editName.value.trim();
	if (trimmed && trimmed !== props.name) {
		emit("rename", trimmed);
	}
	isEditingName.value = false;
}

function cancelEdit() {
	isEditingName.value = false;
}
</script>

<style scoped>
.toolbar-left {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	min-width: 0;
	flex: 1;
}

.workflow-name-group {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	min-width: 0;
}

.workflow-name {
	font-size: 1rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0;
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.workflow-name.editable {
	cursor: pointer;
	border-bottom: 1px dashed transparent;
	transition: border-color 0.15s ease;
}

.workflow-name.editable:hover {
	border-bottom-color: var(--ql-text-muted);
}

.name-input {
	font-size: 1rem;
	font-weight: 600;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-accent);
	border-radius: 0.25rem;
	padding: 0.125rem 0.375rem;
	outline: none;
	min-width: 120px;
}

.status-badge {
	flex-shrink: 0;
	font-size: 0.625rem;
	font-weight: 600;
	padding: 0.125rem 0.5rem;
	border-radius: 9999px;
	text-transform: uppercase;
	letter-spacing: 0.025em;
}

.badge-draft {
	background: var(--ql-subtle);
	color: var(--ql-text-muted);
}
.badge-active {
	background: var(--ql-accent-soft);
	color: var(--ql-success);
}
.badge-paused {
	background: var(--ql-gold-soft);
	color: var(--ql-warning);
}
.badge-archived {
	background: rgba(180, 69, 58, 0.15);
	color: var(--ql-danger);
}
</style>
