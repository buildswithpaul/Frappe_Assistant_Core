<template>
	<Teleport to="body">
		<Transition name="modal-fade">
			<div v-if="files && files.length" class="modal-overlay" @click.self="$emit('cancel')">
				<Transition name="modal-scale" appear>
					<div class="upload-dialog">
						<h3 class="dialog-title">Upload Documents</h3>

						<!-- File list -->
						<div class="file-list">
							<div v-for="(file, i) in files" :key="i" class="file-item">
								<svg
									class="file-icon"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
								>
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
									/>
								</svg>
								<span class="file-name">{{ file.name }}</span>
								<span class="file-size">{{ formatSize(file.size) }}</span>
							</div>
						</div>

						<!-- Visibility selector -->
						<div class="visibility-section">
							<label class="section-label">Visibility</label>
							<div class="visibility-options">
								<label
									class="vis-option"
									:class="{ active: selectedVisibility === 'public' }"
								>
									<input
										type="radio"
										v-model="selectedVisibility"
										value="public"
									/>
									<svg
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
										class="vis-opt-icon"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											stroke-width="2"
											d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
										/>
									</svg>
									<div class="vis-opt-text">
										<span class="vis-opt-label">Public</span>
										<span class="vis-opt-desc">Everyone can search</span>
									</div>
								</label>
								<label
									class="vis-option"
									:class="{ active: selectedVisibility === 'private' }"
								>
									<input
										type="radio"
										v-model="selectedVisibility"
										value="private"
									/>
									<svg
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
										class="vis-opt-icon"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											stroke-width="2"
											d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
										/>
									</svg>
									<div class="vis-opt-text">
										<span class="vis-opt-label">Private</span>
										<span class="vis-opt-desc">Only you can search</span>
									</div>
								</label>
								<label
									class="vis-option"
									:class="{ active: selectedVisibility === 'shared' }"
								>
									<input
										type="radio"
										v-model="selectedVisibility"
										value="shared"
									/>
									<svg
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
										class="vis-opt-icon"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											stroke-width="2"
											d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"
										/>
									</svg>
									<div class="vis-opt-text">
										<span class="vis-opt-label">Shared</span>
										<span class="vis-opt-desc">Choose who can search</span>
									</div>
								</label>
							</div>
						</div>

						<!-- Shared users section -->
						<div v-if="selectedVisibility === 'shared'" class="shared-section">
							<label class="section-label">Share with</label>
							<div class="user-search">
								<input
									v-model="userQuery"
									type="text"
									class="user-search-input"
									placeholder="Type an email to add..."
									@keydown.enter.prevent="addUserFromQuery"
								/>
							</div>
							<div v-if="sharedUsers.length" class="user-chips">
								<span v-for="u in sharedUsers" :key="u" class="user-chip">
									{{ u }}
									<button class="chip-remove" @click="removeUser(u)">
										&times;
									</button>
								</span>
							</div>
							<p
								v-if="selectedVisibility === 'shared' && !sharedUsers.length"
								class="shared-hint"
							>
								Add at least one user to share with.
							</p>
						</div>

						<!-- Actions -->
						<div class="dialog-actions">
							<button class="dialog-btn cancel" @click="$emit('cancel')">
								Cancel
							</button>
							<button
								class="dialog-btn primary"
								@click="handleConfirm"
								:disabled="selectedVisibility === 'shared' && !sharedUsers.length"
							>
								Upload
							</button>
						</div>
					</div>
				</Transition>
			</div>
		</Transition>
	</Teleport>
</template>

<script setup>
import { ref } from "vue";

const props = defineProps({
	files: { type: Array, default: () => [] },
});

const emit = defineEmits(["confirm", "cancel"]);

const selectedVisibility = ref("public");
const sharedUsers = ref([]);
const userQuery = ref("");

function formatSize(bytes) {
	if (bytes < 1024) return bytes + " B";
	if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
	return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

function addUserFromQuery() {
	const email = userQuery.value.trim();
	if (email && !sharedUsers.value.includes(email)) {
		sharedUsers.value.push(email);
	}
	userQuery.value = "";
}

function removeUser(email) {
	sharedUsers.value = sharedUsers.value.filter((u) => u !== email);
}

function handleConfirm() {
	emit("confirm", {
		visibility: selectedVisibility.value,
		sharedWith: selectedVisibility.value === "shared" ? [...sharedUsers.value] : null,
	});
	// Reset state
	selectedVisibility.value = "public";
	sharedUsers.value = [];
	userQuery.value = "";
}
</script>

<style scoped>
.modal-overlay {
	position: fixed;
	inset: 0;
	z-index: 1050;
	display: flex;
	align-items: center;
	justify-content: center;
	background-color: rgba(0, 0, 0, 0.5);
	backdrop-filter: blur(4px);
}

.upload-dialog {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	padding: 1.5rem;
	max-width: 440px;
	width: 90%;
	box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
}

.dialog-title {
	font-size: 1rem;
	font-weight: 600;
	color: var(--ql-text);
	margin-bottom: 1rem;
}

/* File list */
.file-list {
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
	margin-bottom: 1rem;
}

.file-item {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.5rem 0.625rem;
	background: var(--ql-subtle);
	border-radius: 0.5rem;
	font-size: 0.8125rem;
}

.file-icon {
	width: 1rem;
	height: 1rem;
	color: var(--ql-text-muted);
	flex-shrink: 0;
}

.file-name {
	flex: 1;
	min-width: 0;
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
	color: var(--ql-text);
	font-weight: 500;
}

.file-size {
	color: var(--ql-text-muted);
	font-size: 0.75rem;
	flex-shrink: 0;
}

/* Visibility */
.section-label {
	display: block;
	font-size: 0.8125rem;
	font-weight: 600;
	color: var(--ql-text);
	margin-bottom: 0.5rem;
}

.visibility-options {
	display: flex;
	flex-direction: column;
	gap: 0.375rem;
	margin-bottom: 1rem;
}

.vis-option {
	display: flex;
	align-items: center;
	gap: 0.625rem;
	padding: 0.5rem 0.625rem;
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.vis-option:hover {
	border-color: var(--ql-accent);
}

.vis-option.active {
	border-color: var(--ql-accent);
	background: var(--ql-accent-soft);
}

.vis-option input[type="radio"] {
	display: none;
}

.vis-opt-icon {
	width: 1.125rem;
	height: 1.125rem;
	flex-shrink: 0;
	color: var(--ql-text-muted);
}

.vis-option.active .vis-opt-icon {
	color: var(--ql-accent);
}

.vis-opt-text {
	display: flex;
	flex-direction: column;
}

.vis-opt-label {
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text);
}

.vis-opt-desc {
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
}

/* Shared users */
.shared-section {
	margin-bottom: 1rem;
}

.user-search-input {
	width: 100%;
	padding: 0.5rem 0.625rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	outline: none;
	transition: border-color 0.15s ease;
}

.user-search-input:focus {
	border-color: var(--ql-accent);
}

.user-search-input::placeholder {
	color: var(--ql-text-muted);
}

.user-chips {
	display: flex;
	flex-wrap: wrap;
	gap: 0.375rem;
	margin-top: 0.5rem;
}

.user-chip {
	display: inline-flex;
	align-items: center;
	gap: 0.25rem;
	padding: 0.25rem 0.5rem;
	font-size: 0.75rem;
	background: var(--ql-subtle);
	border-radius: 1rem;
	color: var(--ql-text);
}

.chip-remove {
	background: none;
	border: none;
	color: var(--ql-text-muted);
	cursor: pointer;
	font-size: 0.875rem;
	padding: 0;
	line-height: 1;
}

.chip-remove:hover {
	color: var(--ql-danger);
}

.shared-hint {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	margin-top: 0.375rem;
}

/* Actions */
.dialog-actions {
	display: flex;
	justify-content: flex-end;
	gap: 0.5rem;
}

.dialog-btn {
	padding: 0.5rem 1rem;
	font-size: 0.875rem;
	font-weight: 500;
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.dialog-btn.cancel {
	color: var(--ql-text);
	background: var(--ql-subtle);
}

.dialog-btn.cancel:hover {
	background: var(--ql-border);
}

.dialog-btn.primary {
	color: white;
	background: var(--ql-accent);
}

.dialog-btn.primary:hover {
	background: var(--ql-accent-hover);
}

.dialog-btn:disabled {
	opacity: 0.6;
	cursor: not-allowed;
}

/* Transitions */
.modal-fade-enter-active,
.modal-fade-leave-active {
	transition: opacity 0.2s ease;
}
.modal-fade-enter-from,
.modal-fade-leave-to {
	opacity: 0;
}

.modal-scale-enter-active {
	transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1), opacity 0.2s ease;
}
.modal-scale-leave-active {
	transition: transform 0.15s ease, opacity 0.15s ease;
}
.modal-scale-enter-from {
	transform: scale(0.95);
	opacity: 0;
}
.modal-scale-leave-to {
	transform: scale(0.97);
	opacity: 0;
}
</style>
