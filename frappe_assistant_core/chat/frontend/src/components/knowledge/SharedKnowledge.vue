<template>
	<div class="sk-card" :class="{ collapsed: isCollapsed && !isEditing }">
		<!-- Header -->
		<div class="sk-header" @click="toggleCollapse">
			<div class="sk-header-left">
				<button
					class="sk-collapse-btn"
					:title="isCollapsed ? 'Expand' : 'Collapse'"
					:aria-label="isCollapsed ? 'Expand team notes' : 'Collapse team notes'"
				>
					<svg
						class="sk-chevron"
						:class="{ rotated: !isCollapsed }"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M9 5l7 7-7 7"
						/>
					</svg>
				</button>
				<svg class="sk-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="1.5"
						d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
					/>
				</svg>
				<span class="sk-title">Team Notes</span>
				<span v-if="isProcessing" class="sk-status-badge processing">
					<span class="sk-status-dot"></span>
					Processing
				</span>
				<span v-else-if="!loading && totalChunks > 0" class="sk-status-badge completed">
					<svg
						class="sk-check-icon"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M5 13l4 4L19 7"
						/>
					</svg>
					Indexed
				</span>
			</div>
			<div class="sk-header-right" @click.stop>
				<button
					v-if="isAdmin && !isEditing && !loading"
					class="sk-edit-btn"
					@click="startEditing"
					title="Edit team notes"
					aria-label="Edit team notes"
				>
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
						/>
					</svg>
				</button>
			</div>
		</div>

		<!-- Body -->
		<Transition name="sk-collapse">
			<div v-if="!isCollapsed || isEditing" class="sk-body">
				<!-- Loading -->
				<div v-if="loading" class="sk-loading">
					<div class="sk-spinner"></div>
				</div>

				<!-- Error -->
				<div v-else-if="error" class="sk-error">
					<p>{{ error }}</p>
					<button class="sk-retry-btn" @click="load">Retry</button>
				</div>

				<!-- Edit mode -->
				<div v-else-if="isEditing" class="sk-edit-mode">
					<textarea
						v-model="editContent"
						class="sk-editor"
						placeholder="Write team notes in Markdown...&#10;&#10;Notes added here will be embedded and available to the AI for all team members."
						rows="10"
					></textarea>
					<div class="sk-edit-footer">
						<span class="sk-edit-hint">Markdown supported</span>
						<div class="sk-edit-actions">
							<button
								class="sk-btn sk-btn-secondary"
								@click="cancelEditing"
								:disabled="saving"
							>
								Cancel
							</button>
							<button
								class="sk-btn sk-btn-primary"
								@click="handleSave"
								:disabled="saving"
							>
								{{ saving ? "Saving..." : "Save & Embed" }}
							</button>
						</div>
					</div>
				</div>

				<!-- Empty state -->
				<div v-else-if="isEmpty" class="sk-empty">
					<p class="sk-empty-text">No team notes yet.</p>
					<p v-if="isAdmin" class="sk-empty-hint">
						Add notes that your AI assistant can reference for all team members.
					</p>
					<p v-else class="sk-empty-hint">
						Share a memory from your settings to add it here.
					</p>
					<button v-if="isAdmin" class="sk-btn sk-btn-outline" @click="startEditing">
						Add Notes
					</button>
				</div>

				<!-- Content display -->
				<div v-else class="sk-content">
					<div class="sk-markdown" v-html="renderedContent"></div>
				</div>
			</div>
		</Transition>
	</div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from "vue";
import { marked } from "marked";
import DOMPurify from "dompurify";
import { useSharedKnowledge } from "@/composables/useSharedKnowledge";

const props = defineProps({
	isAdmin: { type: Boolean, default: false },
});

const {
	content,
	loading,
	saving,
	error,
	embeddingStatus,
	totalChunks,
	documentId,
	isEditing,
	editContent,
	isEmpty,
	isProcessing,
	load,
	startEditing,
	cancelEditing,
	save,
	shareMemory,
	stopPolling,
} = useSharedKnowledge();

const isCollapsed = ref(true);

function toggleCollapse() {
	if (!isEditing.value) {
		isCollapsed.value = !isCollapsed.value;
	}
}

async function handleSave() {
	const success = await save();
	if (success) {
		isCollapsed.value = false;
	}
}

const renderedContent = computed(() => {
	if (!content.value) return "";
	return DOMPurify.sanitize(marked.parse(content.value));
});

onMounted(load);
onUnmounted(stopPolling);

defineExpose({ load, shareMemory });
</script>

<style scoped>
.sk-card {
	background: transparent;
	border: none;
	border-top: 1px solid var(--ql-border);
	border-radius: 0;
	margin-bottom: 1rem;
	padding-top: 0.25rem;
}

.sk-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 0.625rem 0.25rem;
	cursor: pointer;
	user-select: none;
	border-radius: 0.375rem;
}

.sk-header:hover {
	background: var(--ql-subtle);
}

.sk-header-left {
	display: flex;
	align-items: center;
	gap: 0.5rem;
}

.sk-header-right {
	display: flex;
	align-items: center;
	gap: 0.375rem;
}

.sk-collapse-btn {
	display: flex;
	align-items: center;
	justify-content: center;
	padding: 0;
	background: none;
	border: none;
	cursor: pointer;
	color: var(--ql-text-muted);
}

.sk-chevron {
	width: 1rem;
	height: 1rem;
	transition: transform 0.2s ease;
}

.sk-chevron.rotated {
	transform: rotate(90deg);
}

.sk-icon {
	width: 1.125rem;
	height: 1.125rem;
	color: var(--ql-accent);
	flex-shrink: 0;
}

.sk-title {
	font-size: 0.8125rem;
	font-weight: 600;
	color: var(--ql-text);
}

.sk-status-badge {
	font-size: 0.6875rem;
	padding: 0.125rem 0.5rem;
	border-radius: 1rem;
	font-variant-numeric: tabular-nums;
	display: inline-flex;
	align-items: center;
	gap: 0.375rem;
}

.sk-status-badge.processing {
	color: var(--ql-warning);
	background: rgba(234, 179, 8, 0.1);
}

.sk-status-badge.completed {
	color: var(--ql-success);
	background: rgba(34, 197, 94, 0.08);
}

.sk-check-icon {
	width: 0.75rem;
	height: 0.75rem;
}

.sk-status-dot {
	width: 6px;
	height: 6px;
	border-radius: 50%;
	background: currentColor;
	animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
	0%,
	100% {
		opacity: 1;
	}
	50% {
		opacity: 0.3;
	}
}

.sk-edit-btn {
	display: flex;
	align-items: center;
	justify-content: center;
	padding: 0.25rem;
	background: none;
	border: none;
	border-radius: 0.25rem;
	cursor: pointer;
	color: var(--ql-text-muted);
	transition: color 0.15s, background 0.15s;
}

.sk-edit-btn:hover {
	color: var(--ql-accent);
	background: var(--ql-subtle);
}

/* Collapse transition */
.sk-collapse-enter-active,
.sk-collapse-leave-active {
	transition: opacity 0.2s ease, max-height 0.25s ease;
	overflow: hidden;
}

.sk-collapse-enter-from,
.sk-collapse-leave-to {
	opacity: 0;
	max-height: 0;
}

.sk-collapse-enter-to,
.sk-collapse-leave-from {
	max-height: 600px;
}

.sk-body {
	padding: 0 0.25rem 0.75rem;
}

.sk-loading {
	display: flex;
	justify-content: center;
	padding: 1rem 0;
}

.sk-spinner {
	width: 1.25rem;
	height: 1.25rem;
	border: 2px solid var(--ql-border);
	border-top-color: var(--ql-accent);
	border-radius: 50%;
	animation: spin 0.6s linear infinite;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

.sk-error {
	text-align: center;
	padding: 0.75rem 0;
	color: var(--ql-danger);
	font-size: 0.8125rem;
}

.sk-retry-btn {
	margin-top: 0.5rem;
	padding: 0.25rem 0.75rem;
	font-size: 0.75rem;
	color: var(--ql-accent);
	background: none;
	border: 1px solid var(--ql-accent);
	border-radius: 0.25rem;
	cursor: pointer;
}

/* Edit mode */
.sk-editor {
	width: 100%;
	min-height: 10rem;
	padding: 0.75rem;
	font-family: "SF Mono", "Fira Code", monospace;
	font-size: 0.8125rem;
	line-height: 1.5;
	color: var(--ql-text);
	background: var(--ql-subtle);
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	resize: vertical;
}

.sk-editor:focus {
	outline: none;
	border-color: var(--ql-accent);
	box-shadow: 0 0 0 2px rgba(15, 110, 92, 0.15);
}

.sk-edit-footer {
	display: flex;
	align-items: center;
	justify-content: space-between;
	margin-top: 0.5rem;
}

.sk-edit-hint {
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
}
.sk-edit-actions {
	display: flex;
	gap: 0.5rem;
}

.sk-btn {
	padding: 0.375rem 0.75rem;
	font-size: 0.75rem;
	font-weight: 500;
	border-radius: 0.375rem;
	cursor: pointer;
	transition: all 0.15s;
}

.sk-btn:disabled {
	opacity: 0.5;
	cursor: not-allowed;
}

.sk-btn-primary {
	color: #fff;
	background: var(--ql-accent);
	border: 1px solid var(--ql-accent);
}

.sk-btn-primary:hover:not(:disabled) {
	filter: brightness(1.1);
}

.sk-btn-secondary {
	color: var(--ql-text-secondary);
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
}

.sk-btn-secondary:hover:not(:disabled) {
	background: var(--ql-subtle);
}

.sk-btn-outline {
	color: var(--ql-accent);
	background: transparent;
	border: 1px solid var(--ql-accent);
}

.sk-btn-outline:hover {
	background: var(--ql-accent-soft);
}

/* Empty state */
.sk-empty {
	text-align: center;
	padding: 1rem 0;
}
.sk-empty-text {
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
	margin: 0;
}
.sk-empty-hint {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	margin: 0.375rem 0 0.75rem;
}

/* Content display */
.sk-content {
	padding-top: 0.25rem;
}

.sk-markdown {
	font-size: 0.8125rem;
	line-height: 1.6;
	color: var(--ql-text);
	word-break: break-word;
}

.sk-markdown :deep(h1) {
	font-size: 1.125rem;
	font-weight: 700;
	margin: 1rem 0 0.5rem;
}
.sk-markdown :deep(h2) {
	font-size: 1rem;
	font-weight: 600;
	margin: 0.75rem 0 0.375rem;
}
.sk-markdown :deep(h3) {
	font-size: 0.875rem;
	font-weight: 600;
	margin: 0.5rem 0 0.25rem;
}
.sk-markdown :deep(h4) {
	font-size: 0.8125rem;
	font-weight: 600;
	margin: 0.375rem 0 0.25rem;
}
.sk-markdown :deep(p) {
	margin: 0 0 0.5rem;
}
.sk-markdown :deep(ul),
.sk-markdown :deep(ol) {
	margin: 0.375rem 0;
	padding-left: 1.25rem;
}
.sk-markdown :deep(ul) {
	list-style: disc;
}
.sk-markdown :deep(ol) {
	list-style: decimal;
}
.sk-markdown :deep(li) {
	margin-bottom: 0.25rem;
}

.sk-markdown :deep(code) {
	font-family: "SF Mono", "Fira Code", monospace;
	font-size: 0.75rem;
	background: var(--ql-subtle);
	padding: 0.125rem 0.375rem;
	border-radius: 0.25rem;
}

.sk-markdown :deep(pre) {
	background: var(--ql-subtle);
	padding: 0.75rem;
	border-radius: 0.375rem;
	overflow-x: auto;
	margin: 0.5rem 0;
}

.sk-markdown :deep(pre code) {
	background: none;
	padding: 0;
}
.sk-markdown :deep(strong) {
	font-weight: 600;
}
.sk-markdown :deep(a) {
	color: var(--ql-accent);
	text-decoration: none;
}
.sk-markdown :deep(a:hover) {
	text-decoration: underline;
}

.sk-markdown :deep(blockquote) {
	border-left: 3px solid var(--ql-border);
	padding: 0.375rem 0.75rem;
	margin: 0.5rem 0;
	color: var(--ql-text-secondary);
}

.sk-markdown :deep(table) {
	width: 100%;
	border-collapse: collapse;
	margin: 0.5rem 0;
	font-size: 0.75rem;
}
.sk-markdown :deep(th) {
	background: var(--ql-subtle);
	text-align: left;
	padding: 0.375rem 0.5rem;
	border: 1px solid var(--ql-border);
	font-weight: 600;
}
.sk-markdown :deep(td) {
	padding: 0.375rem 0.5rem;
	border: 1px solid var(--ql-border);
}
.sk-markdown :deep(hr) {
	border: none;
	border-top: 1px solid var(--ql-border);
	margin: 0.75rem 0;
}

.w-4 {
	width: 1rem;
	height: 1rem;
}
</style>
