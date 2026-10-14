<template>
	<div class="project-page" data-test="project-page">
		<div v-if="loading" class="state" data-test="project-loading">{{ __("Loading…") }}</div>

		<div v-else-if="!project" class="state" data-test="project-not-found">
			<p>{{ __("Project not found") }}</p>
			<RouterLink to="/chat" class="back-link">{{ __("Back to chat") }}</RouterLink>
		</div>

		<div v-else class="project-body">
			<header class="project-header">
				<input
					v-if="editing"
					ref="inputRef"
					v-model="draft"
					class="title-input"
					data-test="project-title-input"
					:maxlength="TITLE_MAX_LENGTH"
					:aria-label="__('Rename project')"
					@keydown.enter.prevent="commit"
					@keydown.esc.stop.prevent="cancel"
					@blur="commit"
				/>
				<h1 v-else class="project-title">
					<button class="title-btn" data-test="project-title" @click="start">
						📁 {{ project.title }}
					</button>
				</h1>

				<div ref="menuRootRef" class="header-menu">
					<button
						class="menu-btn"
						data-test="project-menu"
						aria-haspopup="menu"
						:aria-expanded="menuOpen"
						:aria-label="__('Project options')"
						@click="menuOpen = !menuOpen"
					>
						⋯
					</button>
					<div v-if="menuOpen" class="menu" role="menu">
						<button
							class="menu-item danger"
							role="menuitem"
							data-test="project-delete"
							@click="askDelete"
						>
							{{ __("Delete project") }}
						</button>
					</div>
				</div>
			</header>

			<div class="project-grid">
				<ProjectChats :project-id="projectId" :project-title="project.title" />
				<ProjectContext
					:project-id="projectId"
					:instructions="project.instructions || ''"
					:save-instructions="saveInstructions"
					:documents-enabled="projectDocsEnabled"
					:memory-enabled="projectMemoryEnabled"
				/>
			</div>
		</div>

		<ConfirmModal
			data-test="delete-project-modal"
			:open="confirmingDelete"
			:title="__('Delete project')"
			:message="deleteMessage"
			:confirm-label="__('Delete')"
			:cancel-label="__('Cancel')"
			:processing="deleting"
			destructive
			@confirm="removeProject"
			@cancel="confirmingDelete = false"
		/>
	</div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { storeToRefs } from "pinia";
import ConfirmModal from "@/components/common/ConfirmModal.vue";
import ProjectChats from "@/components/projects/ProjectChats.vue";
import ProjectContext from "@/components/projects/ProjectContext.vue";
import { useProjectsStore } from "@/stores/projectsStore";
import { useUserStore } from "@/stores/userStore";
import { useToast } from "@/composables/useToast";
import { useInlineTitleEdit, TITLE_MAX_LENGTH } from "@/composables/useInlineTitleEdit";
import { projectDeleteMessage } from "@/utils/projectDeleteMessage";
import { __ } from "@/utils/i18n";

const props = defineProps({
	projectId: { type: String, required: true },
});

const router = useRouter();
const projectsStore = useProjectsStore();
const { projects } = storeToRefs(projectsStore);
const userStore = useUserStore();
const { showError } = useToast();

const loading = ref(true);
const menuOpen = ref(false);
const menuRootRef = ref(null);
const confirmingDelete = ref(false);
const deleting = ref(false);

// Delete unlinks documents whenever the capability is on, even with RAG off, so the message follows
// the capability alone; the block also needs RAG, because an upload would never be searchable.
const projectDocsCapable = computed(() => userStore.capabilities?.features?.project_documents === true);
const projectDocsEnabled = computed(
	() => projectDocsCapable.value && userStore.capabilities?.features?.rag === true
);
// Same reason as documents: delete clears project memories whenever the capability is on.
const projectMemoryCapable = computed(() => userStore.capabilities?.features?.project_memory === true);
const projectMemoryEnabled = computed(
	() => projectMemoryCapable.value && userStore.capabilities?.features?.memory === true
);
const deleteMessage = computed(() =>
	projectDeleteMessage({ documents: projectDocsCapable.value, memory: projectMemoryCapable.value })
);

const project = computed(() => projects.value.find((p) => p.name === props.projectId) || null);

const { editing, draft, inputRef, start, commit, cancel } = useInlineTitleEdit(
	() => project.value?.title,
	(title) => {
		if (title && title !== project.value?.title) {
			projectsStore.update(props.projectId, { title }).catch(notifyFailure);
		}
	}
);

function notifyFailure(err) {
	showError(err?.message || __("Something went wrong"));
}

async function loadPage(projectId) {
	loading.value = true;
	try {
		if (!projectsStore.byId(projectId)) await projectsStore.load();
	} catch (err) {
		if (projectId === props.projectId) notifyFailure(err);
	} finally {
		if (projectId === props.projectId) loading.value = false;
	}
}

watch(() => props.projectId, loadPage, { immediate: true });

// Rethrows so ProjectInstructions keeps its editor (and the draft) open.
async function saveInstructions(text) {
	try {
		await projectsStore.update(props.projectId, { instructions: text });
	} catch (err) {
		notifyFailure(err);
		throw err;
	}
}

function askDelete() {
	menuOpen.value = false;
	confirmingDelete.value = true;
}

async function removeProject() {
	deleting.value = true;
	try {
		await projectsStore.remove(props.projectId);
		confirmingDelete.value = false;
		router.push("/chat");
	} catch (err) {
		notifyFailure(err);
	} finally {
		deleting.value = false;
	}
}

// Capture phase, like ChatRow: inner controls call .stop, so a bubble listener would miss them.
function onDocumentClick(event) {
	if (menuRootRef.value && !menuRootRef.value.contains(event.target)) menuOpen.value = false;
}

function onDocumentKey(event) {
	if (event.key === "Escape") menuOpen.value = false;
}

function detachListeners() {
	document.removeEventListener("click", onDocumentClick, true);
	document.removeEventListener("keydown", onDocumentKey);
}

watch(menuOpen, (open) => {
	detachListeners();
	if (open) {
		document.addEventListener("click", onDocumentClick, true);
		document.addEventListener("keydown", onDocumentKey);
	}
});
onBeforeUnmount(detachListeners);
</script>

<style scoped>
.project-page {
	flex: 1;
	min-height: 0;
	overflow-y: auto;
	padding: 1.5rem;
}

.project-body {
	max-width: 75rem;
	margin: 0 auto;
	display: flex;
	flex-direction: column;
	gap: 1.25rem;
	container-type: inline-size;
}

.project-grid {
	display: grid;
	grid-template-columns: minmax(0, 1fr);
	gap: 1.5rem;
	align-items: start;
}

@container (min-width: 900px) {
	.project-grid {
		grid-template-columns: minmax(0, 1fr) 320px;
	}
}

.state {
	text-align: center;
	padding: 3rem 1rem;
	color: var(--ql-text-muted);
}

.back-link {
	color: var(--ql-accent);
}

.project-header {
	display: flex;
	align-items: center;
	gap: 0.5rem;
}

.project-title {
	flex: 1;
	min-width: 0;
	font-size: 1.375rem;
	font-weight: 600;
	color: var(--ql-text);
}

.title-btn {
	font: inherit;
	color: inherit;
	background: none;
	border: none;
	padding: 0;
	max-width: 100%;
	text-align: left;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
	cursor: text;
}

.title-input {
	flex: 1;
	min-width: 0;
	font: inherit;
	font-size: 1.375rem;
	font-weight: 600;
	color: var(--ql-text);
	background: var(--ql-surface);
	border: 1px solid var(--ql-accent);
	border-radius: 0.375rem;
	padding: 0 0.375rem;
	outline: none;
}

.header-menu {
	position: relative;
	flex-shrink: 0;
}

.menu-btn {
	padding: 0.25rem 0.625rem;
	font-size: 1.125rem;
	color: var(--ql-text-muted);
	background: none;
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
}

.menu-btn:hover,
.menu-btn[aria-expanded="true"] {
	color: var(--ql-text);
	background-color: var(--ql-subtle);
}

.menu {
	position: absolute;
	right: 0;
	top: 100%;
	z-index: 30;
	min-width: 10rem;
	padding: 0.25rem;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	box-shadow: 0 6px 20px rgba(0, 0, 0, 0.12);
}

.menu-item {
	display: block;
	width: 100%;
	text-align: left;
	padding: 0.375rem 0.625rem;
	font-size: 0.875rem;
	color: var(--ql-text);
	background: none;
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
}

.menu-item:hover {
	background-color: var(--ql-subtle);
}

.menu-item.danger {
	color: var(--ql-danger);
}

</style>
