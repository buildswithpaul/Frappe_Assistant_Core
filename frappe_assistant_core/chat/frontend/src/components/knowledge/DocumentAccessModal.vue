<template>
	<Teleport to="body">
		<Transition name="modal-fade">
			<div v-if="doc" class="modal-overlay" @click.self="$emit('close')">
				<Transition name="modal-scale" appear>
					<div class="access-dialog">
						<div class="dialog-header">
							<h3 class="dialog-title">Manage Access</h3>
							<button class="close-btn" @click="$emit('close')" aria-label="Close">
								<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d="M6 18L18 6M6 6l12 12"
									/>
								</svg>
							</button>
						</div>

						<p class="dialog-subtitle">{{ doc.file_name }}</p>

						<!-- Loading state -->
						<div v-if="loading" class="loading-state">
							<div class="loading-spinner"></div>
							<span>Loading...</span>
						</div>

						<template v-else>
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
								<label class="section-label">Shared with</label>
								<div class="user-search">
									<input
										v-model="userQuery"
										type="text"
										class="user-search-input"
										placeholder="Type an email to add..."
										@keydown.enter.prevent="addUserFromQuery"
									/>
								</div>
								<div v-if="currentSharedUsers.length" class="user-list">
									<div v-for="u in currentSharedUsers" :key="u" class="user-row">
										<span class="user-email">{{ u }}</span>
										<button
											class="remove-btn"
											@click="removeUser(u)"
											title="Remove access"
											aria-label="Remove user access"
										>
											<svg
												fill="none"
												stroke="currentColor"
												viewBox="0 0 24 24"
											>
												<path
													stroke-linecap="round"
													stroke-linejoin="round"
													stroke-width="2"
													d="M6 18L18 6M6 6l12 12"
												/>
											</svg>
										</button>
									</div>
								</div>
								<p v-else class="shared-hint">
									Add at least one user to share with.
								</p>
							</div>

							<!-- Error -->
							<p v-if="error" class="error-text">{{ error }}</p>

							<!-- Actions -->
							<div class="dialog-actions">
								<button class="dialog-btn cancel" @click="$emit('close')">
									Cancel
								</button>
								<button
									class="dialog-btn primary"
									@click="handleSave"
									:disabled="
										saving ||
										(selectedVisibility === 'shared' &&
											!currentSharedUsers.length)
									"
								>
									{{ saving ? "Saving..." : "Save" }}
								</button>
							</div>
						</template>
					</div>
				</Transition>
			</div>
		</Transition>
	</Teleport>
</template>

<script setup>
import { ref, watch } from "vue";
import { api } from "@/api/client";

const props = defineProps({
	doc: { type: Object, default: null },
});

const emit = defineEmits(["close", "updated"]);

const loading = ref(false);
const saving = ref(false);
const error = ref(null);
const selectedVisibility = ref("public");
const currentSharedUsers = ref([]);
const originalSharedUsers = ref([]);
const userQuery = ref("");

// Load document detail when doc changes
watch(
	() => props.doc,
	async (newDoc) => {
		if (!newDoc) return;
		error.value = null;
		selectedVisibility.value = newDoc.visibility || "public";
		currentSharedUsers.value = [];
		originalSharedUsers.value = [];

		if (newDoc.visibility === "shared") {
			loading.value = true;
			try {
				const detail = await api.documents.get(newDoc.document_id);
				if (detail?.shared_with) {
					const users = detail.shared_with.map((s) => s.user_id);
					currentSharedUsers.value = [...users];
					originalSharedUsers.value = [...users];
				}
			} catch (e) {
				error.value = "Failed to load sharing details";
			} finally {
				loading.value = false;
			}
		}
	},
	{ immediate: true }
);

function addUserFromQuery() {
	const email = userQuery.value.trim();
	if (email && !currentSharedUsers.value.includes(email)) {
		currentSharedUsers.value.push(email);
	}
	userQuery.value = "";
}

function removeUser(email) {
	currentSharedUsers.value = currentSharedUsers.value.filter((u) => u !== email);
}

async function handleSave() {
	saving.value = true;
	error.value = null;

	try {
		// Compute add/remove diffs
		const addUsers = currentSharedUsers.value.filter(
			(u) => !originalSharedUsers.value.includes(u)
		);
		const removeUsers = originalSharedUsers.value.filter(
			(u) => !currentSharedUsers.value.includes(u)
		);

		await api.documents.updateAccess(props.doc.document_id, {
			visibility: selectedVisibility.value,
			addUsers: addUsers.length ? addUsers : null,
			removeUsers: removeUsers.length ? removeUsers : null,
		});

		emit("updated");
		emit("close");
	} catch (e) {
		error.value = e.message || "Failed to update access";
	} finally {
		saving.value = false;
	}
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

.access-dialog {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	padding: 1.5rem;
	max-width: 480px;
	width: 90%;
	max-height: 80vh;
	overflow-y: auto;
	box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
}

.dialog-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	margin-bottom: 0.25rem;
}

.dialog-title {
	font-size: 1rem;
	font-weight: 600;
	color: var(--ql-text);
}

.close-btn {
	width: 1.5rem;
	height: 1.5rem;
	padding: 0;
	background: none;
	border: none;
	color: var(--ql-text-muted);
	cursor: pointer;
	border-radius: 0.25rem;
	display: flex;
	align-items: center;
	justify-content: center;
}

.close-btn:hover {
	color: var(--ql-text);
	background: var(--ql-subtle);
}

.close-btn svg {
	width: 1rem;
	height: 1rem;
}

.dialog-subtitle {
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
	margin-bottom: 1rem;
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

/* Loading */
.loading-state {
	display: flex;
	align-items: center;
	justify-content: center;
	gap: 0.5rem;
	padding: 2rem;
	color: var(--ql-text-muted);
	font-size: 0.875rem;
}

.loading-spinner {
	width: 1.25rem;
	height: 1.25rem;
	border: 2px solid var(--ql-border);
	border-top-color: var(--ql-accent);
	border-radius: 50%;
	animation: spin 0.8s linear infinite;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
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

.user-list {
	display: flex;
	flex-direction: column;
	gap: 0.25rem;
	margin-top: 0.5rem;
}

.user-row {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 0.375rem 0.5rem;
	background: var(--ql-subtle);
	border-radius: 0.375rem;
}

.user-email {
	font-size: 0.8125rem;
	color: var(--ql-text);
	min-width: 0;
	overflow: hidden;
	text-overflow: ellipsis;
}

.remove-btn {
	width: 1.25rem;
	height: 1.25rem;
	padding: 0;
	background: none;
	border: none;
	color: var(--ql-text-muted);
	cursor: pointer;
	display: flex;
	align-items: center;
	justify-content: center;
	flex-shrink: 0;
	border-radius: 0.25rem;
}

.remove-btn:hover {
	color: var(--ql-danger);
	background: rgba(239, 68, 68, 0.1);
}

.remove-btn svg {
	width: 0.875rem;
	height: 0.875rem;
}

.shared-hint {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	margin-top: 0.375rem;
}

/* Error */
.error-text {
	font-size: 0.8125rem;
	color: var(--ql-danger);
	margin-bottom: 0.75rem;
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
