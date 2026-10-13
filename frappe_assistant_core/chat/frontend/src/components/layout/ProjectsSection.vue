<template>
	<div v-if="visible" class="projects-section" data-test="projects-section">
		<div class="section-header">
			<h3 class="section-title">{{ __("Projects") }}</h3>
			<button
				class="add-btn"
				data-test="add-project"
				:title="__('New project')"
				:aria-label="__('New project')"
				@click="startCreate"
			>
				＋
			</button>
		</div>

		<input
			v-if="creating"
			ref="inputRef"
			v-model="draft"
			class="project-input"
			data-test="new-project-input"
			maxlength="140"
			:placeholder="__('Project name')"
			:aria-label="__('Project name')"
			:disabled="saving"
			@keydown.enter.prevent="submit"
			@keydown.esc.stop.prevent="cancel"
			@blur="cancel"
		/>

		<div class="project-list">
			<button
				v-for="p in shown"
				:key="p.name"
				class="project-row"
				:class="{ active: route.params.projectId === p.name }"
				data-test="project-row"
				@click="router.push('/chat/project/' + p.name)"
			>
				<span class="project-name">📁 {{ p.title }}</span>
			</button>
			<button
				v-if="projects.length > LIMIT"
				class="show-all"
				data-test="show-all-projects"
				@click="showAll = !showAll"
			>
				{{ showAll ? __("Show fewer") : __("Show all ({0})", [projects.length]) }}
			</button>
		</div>
	</div>
	<button v-else class="empty-add" data-test="add-project" @click="startCreate">
		＋ {{ __("New project") }}
	</button>
</template>

<script setup>
import { computed, nextTick, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { storeToRefs } from "pinia";
import { useProjectsStore } from "@/stores/projectsStore";
import { useToast } from "@/composables/useToast";
import { __ } from "@/utils/i18n";

const LIMIT = 5;

const route = useRoute();
const router = useRouter();
const projectsStore = useProjectsStore();
const { projects } = storeToRefs(projectsStore);
const { showError } = useToast();

const creating = ref(false);
const saving = ref(false);
const draft = ref("");
const showAll = ref(false);
const inputRef = ref(null);

const visible = computed(() => projects.value.length > 0 || creating.value);
const shown = computed(() => (showAll.value ? projects.value : projects.value.slice(0, LIMIT)));

async function startCreate() {
	draft.value = "";
	creating.value = true;
	await nextTick();
	inputRef.value?.focus();
}

function cancel() {
	if (saving.value) return;
	creating.value = false;
}

async function submit() {
	const title = draft.value.trim().split(/\s+/).join(" ");
	if (!title || saving.value) return;
	saving.value = true;
	try {
		const project = await projectsStore.create(title);
		creating.value = false;
		router.push("/chat/project/" + project.name);
	} catch (err) {
		showError(err?.message || __("Something went wrong"));
	} finally {
		saving.value = false;
	}
}
</script>

<style scoped>
.projects-section {
	flex-shrink: 0;
	border-bottom: 1px solid var(--ql-border);
	padding-bottom: 0.25rem;
}

.section-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 0.5rem 0.75rem;
}

.section-title {
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.05em;
}

.add-btn {
	padding: 0 0.375rem;
	color: var(--ql-text-muted);
	background: none;
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
}

.add-btn:hover {
	color: var(--ql-text);
	background-color: var(--ql-subtle);
}

.project-input {
	display: block;
	width: calc(100% - 1rem);
	margin: 0 0.5rem 0.25rem;
	font-size: 0.875rem;
	color: var(--ql-text);
	background: var(--ql-surface);
	border: 1px solid var(--ql-accent);
	border-radius: 0.375rem;
	padding: 0.25rem 0.5rem;
	outline: none;
}

.project-list {
	max-height: 14rem;
	overflow-y: auto;
	padding: 0 0.5rem;
}

.project-row {
	display: block;
	width: 100%;
	text-align: left;
	padding: 0.375rem 0.75rem;
	font-size: 0.875rem;
	color: var(--ql-text);
	background: none;
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
}

.project-row:hover {
	background-color: var(--ql-subtle);
}

.project-row.active {
	background-color: var(--ql-accent-soft);
}

.project-name {
	display: block;
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.show-all {
	padding: 0.25rem 0.75rem;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	background: none;
	border: none;
	cursor: pointer;
}

.show-all:hover {
	color: var(--ql-text);
}

.empty-add {
	flex-shrink: 0;
	text-align: left;
	margin: 0.25rem 0.5rem;
	padding: 0.375rem 0.75rem;
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
	background: none;
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
}

.empty-add:hover {
	color: var(--ql-text);
	background-color: var(--ql-subtle);
}
</style>
