<template>
	<div class="narrative">
		<div v-for="section in sections" :key="section.key" class="narrative-section">
			<h4 class="narrative-heading">{{ section.title }}</h4>
			<p class="narrative-paragraph">
				<span
					v-for="sentence in section.sentences"
					:key="sentence.memoryId"
					class="memory-sentence"
					:class="{
						'is-active': activeSentence === sentence.memoryId,
						'is-confirming': confirmingId === sentence.memoryId,
						'is-fading': fadingId === sentence.memoryId,
					}"
					@mouseenter="onMouseEnter(sentence.memoryId)"
					@mouseleave="onMouseLeave"
					@click.stop="onTap(sentence.memoryId)"
				>
					<!-- Inline editor (when editing this sentence) -->
					<span v-if="editingId === sentence.memoryId" class="inline-editor" @click.stop>
						<textarea
							ref="editTextarea"
							v-model="editText"
							class="edit-textarea"
							rows="2"
							maxlength="500"
							@keydown.enter.prevent="saveEdit"
							@keydown.escape="cancelEdit"
						/>
						<span class="edit-actions">
							<button
								class="edit-save-btn"
								:disabled="!editText.trim() || editText.trim() === sentence.text"
								@click.stop="saveEdit"
							>
								Save
							</button>
							<button class="edit-cancel-btn" @click.stop="cancelEdit">
								Cancel
							</button>
						</span>
					</span>
					<!-- Normal text -->
					<template v-else>{{ sentence.text }}</template>
					<!-- Action popover -->
					<transition name="popover-fade">
						<span
							v-if="
								activeSentence === sentence.memoryId &&
								!confirmingId &&
								editingId !== sentence.memoryId
							"
							class="sentence-actions"
							@mouseenter="popoverHovered = true"
							@mouseleave="popoverMouseLeave"
						>
							<button
								class="action-btn edit-btn"
								title="Edit memory"
								aria-label="Edit memory"
								@click.stop="startEdit(sentence.memoryId, sentence.text)"
							>
								<svg
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
									width="14"
									height="14"
								>
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
									/>
								</svg>
							</button>
							<button
								class="action-btn share-btn"
								title="Share to team"
								aria-label="Share memory to team"
								@click.stop="startConfirm(sentence.memoryId, 'share')"
							>
								<svg
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
									width="14"
									height="14"
								>
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"
									/>
								</svg>
							</button>
							<button
								class="action-btn delete-btn"
								title="Delete memory"
								aria-label="Delete memory"
								@click.stop="startConfirm(sentence.memoryId, 'delete')"
							>
								<svg
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
									width="14"
									height="14"
								>
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
									/>
								</svg>
							</button>
						</span>
					</transition>

					<!-- Confirm popover -->
					<transition name="popover-fade">
						<span
							v-if="confirmingId === sentence.memoryId"
							class="sentence-actions confirm-popover"
							@mouseenter="popoverHovered = true"
							@mouseleave="popoverMouseLeave"
						>
							<span class="confirm-label">
								{{ confirmAction === "share" ? "Share to team?" : "Delete?" }}
							</span>
							<button
								class="confirm-btn confirm-yes"
								:class="{ 'confirm-share': confirmAction === 'share' }"
								:disabled="actionInProgress"
								@click.stop="executeConfirm"
							>
								{{ actionInProgress ? "..." : "Yes" }}
							</button>
							<button class="confirm-btn confirm-no" @click.stop="cancelConfirm">
								No
							</button>
						</span>
					</transition>
				</span>
			</p>
		</div>
	</div>
</template>

<script setup>
import { ref } from "vue";

const props = defineProps({
	sections: {
		type: Array,
		required: true,
	},
});

const emit = defineEmits(["delete", "share", "edit"]);

// Hover / active state
const activeSentence = ref(null);
const popoverHovered = ref(false);
let leaveTimer = null;

// Confirm state
const confirmingId = ref(null);
const confirmAction = ref(null); // 'share' | 'delete'
const actionInProgress = ref(false);
const fadingId = ref(null);

// Edit state
const editingId = ref(null);
const editText = ref("");

// Touch detection
const isTouchDevice = ref(false);

function onMouseEnter(memoryId) {
	if (isTouchDevice.value) return;
	clearTimeout(leaveTimer);
	if (!confirmingId.value) {
		activeSentence.value = memoryId;
	}
}

function onMouseLeave() {
	if (isTouchDevice.value) return;
	popoverHovered.value = false;
	leaveTimer = setTimeout(() => {
		if (!popoverHovered.value && !confirmingId.value) {
			activeSentence.value = null;
		}
	}, 150);
}

function popoverMouseLeave() {
	popoverHovered.value = false;
	leaveTimer = setTimeout(() => {
		if (!popoverHovered.value && !confirmingId.value) {
			activeSentence.value = null;
		}
	}, 150);
}

function onTap(memoryId) {
	// First touch sets the flag for future interactions
	isTouchDevice.value = "ontouchstart" in window;

	if (isTouchDevice.value) {
		if (activeSentence.value === memoryId) {
			// Second tap deselects
			activeSentence.value = null;
			confirmingId.value = null;
		} else {
			activeSentence.value = memoryId;
			confirmingId.value = null;
		}
	}
}

function startEdit(memoryId, text) {
	editingId.value = memoryId;
	editText.value = text;
	activeSentence.value = null;
	confirmingId.value = null;
}

function cancelEdit() {
	editingId.value = null;
	editText.value = "";
}

function saveEdit() {
	const content = editText.value.trim();
	if (!content || !editingId.value) return;
	emit("edit", { memoryId: editingId.value, content });
	editingId.value = null;
	editText.value = "";
}

function startConfirm(memoryId, action) {
	confirmingId.value = memoryId;
	confirmAction.value = action;
}

function cancelConfirm() {
	confirmingId.value = null;
	confirmAction.value = null;
	activeSentence.value = null;
}

async function executeConfirm() {
	if (actionInProgress.value) return;
	actionInProgress.value = true;

	const memoryId = confirmingId.value;
	const action = confirmAction.value;

	try {
		if (action === "delete") {
			fadingId.value = memoryId;
			// Small delay for the fade animation
			await new Promise((r) => setTimeout(r, 200));
			emit("delete", memoryId);
		} else if (action === "share") {
			emit("share", memoryId);
		}
	} finally {
		actionInProgress.value = false;
		confirmingId.value = null;
		confirmAction.value = null;
		activeSentence.value = null;
		// Clear fade after a tick so Vue removes the element
		setTimeout(() => {
			fadingId.value = null;
		}, 50);
	}
}
</script>

<style scoped>
.narrative {
	display: flex;
	flex-direction: column;
	gap: 1.5rem;
}

.narrative-section {
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
}

.narrative-heading {
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.04em;
	margin: 0;
}

.narrative-paragraph {
	font-size: 0.875rem;
	color: var(--ql-text);
	line-height: 1.7;
	margin: 0;
}

/* Each sentence is an inline span within the paragraph */
.memory-sentence {
	position: relative;
	border-radius: 3px;
	transition: background-color 0.15s ease;
	cursor: default;
	padding: 1px 2px;
	margin: 0 1px;
}

.memory-sentence.is-active,
.memory-sentence.is-confirming {
	background: var(--ql-accent-soft);
}

.memory-sentence.is-fading {
	opacity: 0;
	transition: opacity 0.2s ease;
}

/* Action popover — appears below the sentence */
.sentence-actions {
	position: absolute;
	bottom: calc(100% + 4px);
	left: 50%;
	transform: translateX(-50%);
	display: inline-flex;
	align-items: center;
	gap: 2px;
	padding: 3px 4px;
	background: var(--ql-surface, #fff);
	border: 1px solid var(--ql-border);
	border-radius: 6px;
	box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
	white-space: nowrap;
	z-index: 10;
}

.confirm-popover {
	gap: 4px;
	padding: 3px 6px;
}

.action-btn {
	display: flex;
	align-items: center;
	justify-content: center;
	padding: 4px;
	background: none;
	border: none;
	border-radius: 4px;
	color: var(--ql-text-muted);
	cursor: pointer;
	transition: all 0.12s ease;
}

.action-btn.edit-btn:hover {
	color: #f59e0b;
	background: rgba(245, 158, 11, 0.1);
}

.action-btn.share-btn:hover {
	color: var(--ql-accent);
	background: var(--ql-accent-soft);
}

.action-btn.delete-btn:hover {
	color: #ef4444;
	background: rgba(239, 68, 68, 0.1);
}

.confirm-label {
	font-size: 0.7rem;
	color: var(--ql-text-muted);
	padding-right: 2px;
}

.confirm-btn {
	padding: 2px 8px;
	font-size: 0.7rem;
	font-weight: 500;
	border: none;
	border-radius: 4px;
	cursor: pointer;
	transition: background 0.12s ease;
}

.confirm-yes {
	background: rgba(239, 68, 68, 0.12);
	color: #ef4444;
}

.confirm-yes:hover {
	background: rgba(239, 68, 68, 0.2);
}

.confirm-yes.confirm-share {
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
}

.confirm-yes.confirm-share:hover {
	background: var(--ql-accent-soft);
}

.confirm-yes:disabled {
	opacity: 0.5;
	cursor: not-allowed;
}

.confirm-no {
	background: var(--ql-subtle, #f5f5f5);
	color: var(--ql-text-muted);
}

.confirm-no:hover {
	color: var(--ql-text);
}

/* Popover transition */
.popover-fade-enter-active,
.popover-fade-leave-active {
	transition: opacity 0.1s ease;
}

.popover-fade-enter-from,
.popover-fade-leave-to {
	opacity: 0;
}

/* Inline editor */
.inline-editor {
	display: block;
	margin: 0.25rem 0;
}

.edit-textarea {
	display: block;
	width: 100%;
	padding: 0.5rem;
	font-size: 0.85rem;
	font-family: inherit;
	line-height: 1.5;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-accent);
	border-radius: 0.375rem;
	resize: vertical;
	outline: none;
	box-shadow: 0 0 0 3px var(--ql-accent-soft);
}

.edit-actions {
	display: flex;
	gap: 0.375rem;
	margin-top: 0.375rem;
}

.edit-save-btn,
.edit-cancel-btn {
	padding: 0.25rem 0.625rem;
	font-size: 0.75rem;
	font-weight: 500;
	border-radius: 0.25rem;
	border: none;
	cursor: pointer;
	transition: all 0.12s ease;
}

.edit-save-btn {
	background: var(--ql-accent);
	color: white;
}

.edit-save-btn:hover:not(:disabled) {
	opacity: 0.9;
}

.edit-save-btn:disabled {
	opacity: 0.4;
	cursor: not-allowed;
}

.edit-cancel-btn {
	background: var(--ql-subtle, #f5f5f5);
	color: var(--ql-text-muted);
}

.edit-cancel-btn:hover {
	color: var(--ql-text);
}
</style>
