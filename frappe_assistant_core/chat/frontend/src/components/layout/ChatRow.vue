<template>
	<div
		ref="rootRef"
		class="conversation-item"
		data-test="chat-row"
		:title="rowTitle"
		:class="{ active, confirming, deleting }"
		@click="!renaming && !confirming && $emit('select')"
	>
		<div v-if="confirming" class="confirm-delete">
			<span class="confirm-text">{{ __("Archive?") }}</span>
			<div class="confirm-actions">
				<button
					class="confirm-btn confirm-yes"
					data-test="confirm-archive"
					:title="__('Confirm archive')"
					:aria-label="__('Confirm archive')"
					@click.stop="onArchive"
				>
					<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
					</svg>
				</button>
				<button
					class="confirm-btn confirm-no"
					data-test="cancel-archive"
					:title="__('Cancel')"
					:aria-label="__('Cancel archive')"
					@click.stop="confirming = false"
				>
					<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
					</svg>
				</button>
			</div>
		</div>

		<template v-else>
			<div class="conversation-content">
				<input
					v-if="renaming"
					ref="inputRef"
					v-model="draft"
					class="rename-input"
					data-test="rename-input"
					maxlength="140"
					:aria-label="__('Rename chat')"
					@click.stop
					@keydown.enter.prevent="commit"
					@keydown.esc.stop.prevent="cancel"
					@blur="commit"
				/>
				<div v-else class="conversation-title">
					<span
						v-if="showProject && session.project_title"
						class="project-dot"
						data-test="project-dot"
						:title="session.project_title"
						:aria-label="session.project_title"
					/>
					<span class="title-text">{{ displayTitle }}</span>
				</div>
				<div v-if="showTime" class="conversation-time">{{ timeLabel }}</div>
			</div>

			<div v-if="deleting" class="delete-spinner">
				<div class="animate-spin w-3.5 h-3.5 border-2 border-red-400 border-t-transparent rounded-full"></div>
			</div>
			<button
				v-else
				class="row-menu"
				data-test="row-menu"
				aria-haspopup="menu"
				:aria-expanded="menuOpen"
				:aria-label="__('Chat options')"
				@click.stop="toggleMenu"
			>
				<svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
					<circle cx="5" cy="12" r="1.8" />
					<circle cx="12" cy="12" r="1.8" />
					<circle cx="19" cy="12" r="1.8" />
				</svg>
			</button>

			<ChatRowMenu
				v-if="menuOpen"
				:session="session"
				:projects="projects"
				:allow-new-project="allowNewProject"
				@rename="startRename"
				@move="moveTo"
				@new-project="newProject"
				@archive="askArchive"
			/>
		</template>
	</div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import ChatRowMenu from "./ChatRowMenu.vue";
import { __ } from "@/utils/i18n";
import { formatConversationTime } from "@/utils/formatConversationTime";

const props = defineProps({
	session: { type: Object, required: true },
	active: { type: Boolean, default: false },
	deleting: { type: Boolean, default: false },
	projects: { type: Array, default: () => [] },
	showProject: { type: Boolean, default: true },
	showTime: { type: Boolean, default: false },
	allowNewProject: { type: Boolean, default: true },
});

const emit = defineEmits(["select", "rename", "move", "new-project", "archive"]);

const displayTitle = computed(() => props.session.title || props.session.preview || __("New conversation"));
const timeLabel = computed(() => formatConversationTime(props.session.last_activity || props.session.modified));
const rowTitle = computed(() => (timeLabel.value ? `${displayTitle.value} · ${timeLabel.value}` : displayTitle.value));

const rootRef = ref(null);
const inputRef = ref(null);
const menuOpen = ref(false);
const confirming = ref(false);
const renaming = ref(false);
const draft = ref("");

function closeMenu() {
	menuOpen.value = false;
}

function toggleMenu() {
	if (menuOpen.value) closeMenu();
	else menuOpen.value = true;
}

function onDocumentClick(event) {
	if (rootRef.value && !rootRef.value.contains(event.target)) {
		closeMenu();
		confirming.value = false;
	}
}

function onDocumentKey(event) {
	if (event.key === "Escape") {
		closeMenu();
		confirming.value = false;
	}
}

function detachListeners() {
	document.removeEventListener("click", onDocumentClick, true);
	document.removeEventListener("keydown", onDocumentKey);
}

// Capture phase: the menu, button and rename input call .stop, so a bubble listener on
// another row would never see a click on this row and both would stay open.
watch([menuOpen, confirming], ([menu, confirm]) => {
	detachListeners();
	if (menu || confirm) {
		document.addEventListener("click", onDocumentClick, true);
		document.addEventListener("keydown", onDocumentKey);
	}
});
onBeforeUnmount(detachListeners);

async function startRename() {
	closeMenu();
	draft.value = props.session.title || "";
	renaming.value = true;
	await nextTick();
	inputRef.value?.focus();
	inputRef.value?.select();
}

function commit() {
	if (!renaming.value) return;
	renaming.value = false;
	emit("rename", draft.value.trim().split(/\s+/).join(" "));
}

function cancel() {
	renaming.value = false;
}

function moveTo(projectId) {
	closeMenu();
	emit("move", projectId);
}

function newProject() {
	closeMenu();
	emit("new-project");
}

function askArchive() {
	closeMenu();
	confirming.value = true;
}

function onArchive() {
	confirming.value = false;
	emit("archive");
}
</script>

<style scoped>
.conversation-item {
	position: relative;
	padding: 0.5rem 0.75rem;
	border-radius: 0.5rem;
	cursor: pointer;
	margin-bottom: 0.25rem;
	transition: all 0.15s ease;
	display: flex;
	align-items: center;
	gap: 0.25rem;
}

.conversation-item:hover {
	background-color: var(--ql-subtle);
}

.conversation-item.active {
	background-color: var(--ql-accent-soft);
	border-left: 3px solid var(--ql-accent);
}

.conversation-item.confirming {
	background-color: rgba(239, 68, 68, 0.08);
}

.conversation-item.deleting {
	opacity: 0.5;
	pointer-events: none;
}

.conversation-content {
	flex: 1;
	min-width: 0;
}

.conversation-title {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
}

.title-text {
	min-width: 0;
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.project-dot {
	width: 6px;
	height: 6px;
	border-radius: 50%;
	background-color: var(--ql-accent);
	flex: none;
}

.conversation-time {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	margin-top: 0.125rem;
}


.rename-input {
	width: 100%;
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
	background: var(--ql-surface);
	border: 1px solid var(--ql-accent);
	border-radius: 0.25rem;
	padding: 0 0.25rem;
	outline: none;
}

.row-menu {
	flex-shrink: 0;
	padding: 0.25rem;
	color: var(--ql-text-muted);
	background: none;
	border: none;
	border-radius: 0.25rem;
	cursor: pointer;
	opacity: 0;
	transition: all 0.15s ease;
}

.conversation-item:hover .row-menu,
.row-menu:focus-visible,
.row-menu[aria-expanded="true"] {
	opacity: 1;
}

@media (hover: none) {
	.row-menu {
		opacity: 1;
	}
}

.row-menu:hover {
	color: var(--ql-text);
	background-color: var(--ql-subtle);
}

.delete-spinner {
	flex-shrink: 0;
	padding: 0.25rem;
}

.confirm-delete {
	display: flex;
	align-items: center;
	justify-content: space-between;
	width: 100%;
}

.confirm-text {
	font-size: 0.8rem;
	font-weight: 500;
	color: #ef4444;
}

.confirm-actions {
	display: flex;
	gap: 0.25rem;
}

.confirm-btn {
	padding: 0.25rem;
	border: none;
	border-radius: 0.25rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.confirm-yes {
	color: #ef4444;
	background-color: rgba(239, 68, 68, 0.1);
}

.confirm-yes:hover {
	background-color: rgba(239, 68, 68, 0.2);
}

.confirm-no {
	color: var(--ql-text-muted);
	background: none;
}

.confirm-no:hover {
	color: var(--ql-text);
	background-color: var(--ql-subtle);
}
</style>
