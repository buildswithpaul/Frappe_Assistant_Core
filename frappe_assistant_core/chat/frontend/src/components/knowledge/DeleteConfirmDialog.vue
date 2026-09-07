<template>
	<Teleport to="body">
		<Transition name="modal-fade">
			<div v-if="doc" class="modal-overlay" @click.self="$emit('cancel')">
				<Transition name="modal-scale" appear>
					<div class="confirm-dialog">
						<h3 class="confirm-title">Delete Document</h3>
						<p class="confirm-message">
							Are you sure you want to delete <strong>{{ doc.file_name }}</strong
							>? This will remove the document and all its embeddings.
						</p>
						<div class="confirm-actions">
							<button class="confirm-btn cancel" @click="$emit('cancel')">
								Cancel
							</button>
							<button
								class="confirm-btn danger"
								@click="$emit('confirm')"
								:disabled="deleting"
							>
								{{ deleting ? "Deleting..." : "Delete" }}
							</button>
						</div>
					</div>
				</Transition>
			</div>
		</Transition>
	</Teleport>
</template>

<script setup>
defineProps({
	doc: { type: Object, default: null },
	deleting: { type: Boolean, default: false },
});

defineEmits(["cancel", "confirm"]);
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

.confirm-dialog {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	padding: 1.5rem;
	max-width: 400px;
	width: 90%;
	box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
}

.confirm-title {
	font-size: 1rem;
	font-weight: 600;
	color: var(--ql-text);
	margin-bottom: 0.75rem;
}

.confirm-message {
	font-size: 0.875rem;
	color: var(--ql-text-secondary);
	line-height: 1.5;
	margin-bottom: 1.25rem;
}

.confirm-actions {
	display: flex;
	justify-content: flex-end;
	gap: 0.5rem;
}

.confirm-btn {
	padding: 0.5rem 1rem;
	font-size: 0.875rem;
	font-weight: 500;
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.confirm-btn.cancel {
	color: var(--ql-text);
	background: var(--ql-subtle);
}

.confirm-btn.cancel:hover {
	background: var(--ql-border);
}

.confirm-btn.danger {
	color: white;
	background: var(--ql-danger);
}

.confirm-btn.danger:hover {
	background: #dc2626;
}

.confirm-btn:disabled {
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
