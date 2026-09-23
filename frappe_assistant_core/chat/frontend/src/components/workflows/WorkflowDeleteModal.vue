<template>
	<Teleport to="body">
		<div
			v-if="modelValue"
			class="modal-overlay"
			@click.self="$emit('update:modelValue', false)"
		>
			<div class="modal-content">
				<h2 class="modal-title">Delete Agent</h2>
				<p class="modal-text">
					Are you sure you want to delete <strong>{{ workflow?.workflow_name }}</strong
					>? This will archive the agent and stop any scheduled runs.
				</p>
				<div class="modal-actions">
					<button @click="$emit('update:modelValue', false)" class="action-btn">
						Cancel
					</button>
					<button
						@click="$emit('confirm')"
						class="action-btn danger"
						:disabled="isDeleting"
					>
						{{ isDeleting ? "Deleting..." : "Delete" }}
					</button>
				</div>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
defineProps({
	modelValue: { type: Boolean, default: false },
	workflow: { type: Object, default: null },
	isDeleting: { type: Boolean, default: false },
});

defineEmits(["update:modelValue", "confirm"]);
</script>

<style scoped>
.modal-overlay {
	position: fixed;
	inset: 0;
	background: rgba(0, 0, 0, 0.5);
	display: flex;
	align-items: center;
	justify-content: center;
	z-index: 1050;
	padding: 1rem;
}

.modal-content {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	padding: 1.5rem;
	width: 100%;
	max-width: 28rem;
	box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.modal-title {
	font-size: 1.125rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0 0 1.25rem;
}

.modal-text {
	font-size: 0.875rem;
	color: var(--ql-text-secondary);
	margin: 0 0 1.25rem;
	line-height: 1.5;
}

.modal-actions {
	display: flex;
	justify-content: flex-end;
	gap: 0.5rem;
	margin-top: 1.25rem;
}

.action-btn {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.5rem 0.875rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
	background: var(--ql-subtle);
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.action-btn:hover {
	background-color: var(--ql-border);
}
.action-btn.danger {
	color: white;
	background-color: var(--ql-danger);
}
.action-btn.danger:hover {
	opacity: 0.9;
}
.action-btn:disabled {
	opacity: 0.6;
	cursor: not-allowed;
}
</style>
