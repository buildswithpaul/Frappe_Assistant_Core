<template>
	<section class="project-memory" data-test="project-memory">
		<header class="memory-header">
			<h2 class="memory-title">{{ __("Memory") }}</h2>
			<button
				v-if="memories.length && !loadFailed"
				class="clear-btn"
				data-test="memory-clear"
				@click="confirmingClear = true"
			>
				{{ __("Clear project memory") }}
			</button>
		</header>

		<div v-if="loadFailed" class="load-error" data-test="memory-error">
			<span>{{ __("Couldn't load this project's memories.") }}</span>
			<button class="clear-btn" data-test="memory-retry" @click="loadMemories">{{ __("Retry") }}</button>
		</div>
		<p v-else-if="!loading && !memories.length" class="empty" data-test="memory-empty">
			{{
				__(
					"Nothing remembered for this project yet. As you chat here, FACO keeps project-specific facts in this list."
				)
			}}
		</p>
		<ul v-else class="memory-list">
			<ProjectMemoryRow
				v-for="memory in memories"
				:key="memory.memory_id"
				:memory="memory"
				@edit="updateMemory"
				@delete="deleteTarget = memory"
			/>
		</ul>

		<ConfirmModal
			:open="!!deleteTarget"
			:title="__('Delete memory')"
			:message="__('Delete this memory? FACO will no longer use it in this project.')"
			:confirm-label="__('Delete')"
			:cancel-label="__('Cancel')"
			:processing="busy"
			destructive
			@confirm="removeMemory"
			@cancel="deleteTarget = null"
		/>
		<ConfirmModal
			:open="confirmingClear"
			:title="__('Clear project memory')"
			:message="__('Delete every memory FACO has kept for this project? This cannot be undone.')"
			:confirm-label="__('Clear')"
			:cancel-label="__('Cancel')"
			:processing="busy"
			destructive
			@confirm="clearAll"
			@cancel="confirmingClear = false"
		/>
	</section>
</template>

<script setup>
import { ref, watch } from "vue";
import ConfirmModal from "@/components/common/ConfirmModal.vue";
import ProjectMemoryRow from "@/components/projects/ProjectMemoryRow.vue";
import { api } from "@/api/client";
import { useToast } from "@/composables/useToast";
import { __ } from "@/utils/i18n";

// A project holds a handful of facts; one page covers it, and the block never polls.
const PAGE_SIZE = 200;

const props = defineProps({
	projectId: { type: String, required: true },
});

const { showError } = useToast();

const memories = ref([]);
const loading = ref(true);
const loadFailed = ref(false);
const deleteTarget = ref(null);
const confirmingClear = ref(false);
const busy = ref(false);

function notifyFailure(err) {
	showError(err?.message || __("Something went wrong"));
}

async function loadMemories() {
	const projectId = props.projectId;
	loading.value = true;
	try {
		const result = await api.memories.list(null, PAGE_SIZE, 0, projectId);
		if (projectId !== props.projectId) return;
		memories.value = result?.memories || [];
		loadFailed.value = false;
	} catch (err) {
		if (projectId !== props.projectId) return;
		loadFailed.value = true;
		notifyFailure(err);
	} finally {
		if (projectId === props.projectId) loading.value = false;
	}
}

watch(
	() => props.projectId,
	() => {
		memories.value = [];
		loadFailed.value = false;
		deleteTarget.value = null;
		confirmingClear.value = false;
		loadMemories();
	},
	{ immediate: true }
);

async function updateMemory({ memoryId, content, onSaved }) {
	try {
		await api.memories.update(memoryId, content);
		const memory = memories.value.find((m) => m.memory_id === memoryId);
		if (memory) memory.content = content;
		onSaved();
	} catch (err) {
		notifyFailure(err);
	}
}

async function removeMemory() {
	const target = deleteTarget.value;
	busy.value = true;
	try {
		await api.memories.delete(target.memory_id);
		memories.value = memories.value.filter((m) => m.memory_id !== target.memory_id);
		deleteTarget.value = null;
	} catch (err) {
		notifyFailure(err);
	} finally {
		busy.value = false;
	}
}

async function clearAll() {
	busy.value = true;
	try {
		await api.memories.clearProject(props.projectId);
		memories.value = [];
		confirmingClear.value = false;
	} catch (err) {
		notifyFailure(err);
	} finally {
		busy.value = false;
	}
}
</script>

<style scoped>
.project-memory {
	display: flex;
	flex-direction: column;
	gap: 0.625rem;
	padding: 0.875rem;
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	background: var(--ql-surface);
}

.memory-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 0.75rem;
}

.memory-title {
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.05em;
}

.clear-btn {
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
	background: var(--ql-subtle);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	padding: 0.375rem 0.75rem;
	cursor: pointer;
}

.empty {
	color: var(--ql-text-muted);
	font-size: 0.875rem;
}

.memory-list {
	list-style: none;
	margin: 0;
	padding: 0;
	display: flex;
	flex-direction: column;
}

.load-error {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 0.75rem;
	font-size: 0.875rem;
	color: var(--ql-danger);
}
</style>
