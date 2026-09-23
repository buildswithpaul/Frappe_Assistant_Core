<template>
	<Teleport to="body">
		<div v-if="open" class="modal-overlay" @click.self="$emit('cancel')">
			<div class="confirm-modal" :class="{ 'is-destructive': destructive }">
				<h3 class="confirm-title">{{ title }}</h3>
				<p v-if="message" class="confirm-text">{{ message }}</p>
				<p v-if="warning" class="confirm-warning">{{ warning }}</p>
				<div class="confirm-actions">
					<button class="btn-secondary" @click="$emit('cancel')" :disabled="processing">
						{{ cancelLabel }}
					</button>
					<button
						class="btn-primary"
						:class="{ 'is-destructive': destructive }"
						@click="$emit('confirm')"
						:disabled="processing"
					>
						{{ processing ? processingLabel : confirmLabel }}
					</button>
				</div>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
defineProps({
	open: { type: Boolean, default: false },
	title: { type: String, required: true },
	message: { type: String, default: "" },
	warning: { type: String, default: "" },
	confirmLabel: { type: String, default: "Confirm" },
	cancelLabel: { type: String, default: "Cancel" },
	processingLabel: { type: String, default: "Processing..." },
	processing: { type: Boolean, default: false },
	destructive: { type: Boolean, default: false },
});

defineEmits(["confirm", "cancel"]);
</script>

<style scoped>
.modal-overlay {
	position: fixed;
	inset: 0;
	background: rgba(0, 0, 0, 0.5);
	display: flex;
	align-items: center;
	justify-content: center;
	z-index: 1200;
	padding: 1rem;
}

.confirm-modal {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	width: 100%;
	max-width: 420px;
	padding: 1.5rem;
	box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}

.confirm-title {
	font-size: 1.0625rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0 0 0.75rem;
}

.confirm-text {
	font-size: 0.875rem;
	color: var(--ql-text);
	margin: 0 0 0.5rem;
	line-height: 1.5;
}

.confirm-warning {
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
	margin: 0.5rem 0 1rem;
	line-height: 1.5;
}

.confirm-actions {
	display: flex;
	gap: 0.75rem;
	justify-content: flex-end;
	margin-top: 1.25rem;
}

.btn-secondary {
	padding: 0.5rem 1rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
	background: transparent;
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.btn-secondary:hover:not(:disabled) {
	background: var(--ql-subtle);
}

.btn-secondary:disabled {
	opacity: 0.6;
	cursor: not-allowed;
}

.btn-primary {
	padding: 0.5rem 1rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: white;
	background: var(--ql-accent);
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.btn-primary:hover:not(:disabled) {
	background: var(--ql-accent-hover);
}

.btn-primary.is-destructive {
	background: #dc2626;
}

.btn-primary.is-destructive:hover:not(:disabled) {
	background: #b91c1c;
}

.btn-primary:disabled {
	opacity: 0.6;
	cursor: not-allowed;
}

@media (max-width: 640px) {
	.confirm-actions {
		flex-direction: column-reverse;
	}
	.btn-primary,
	.btn-secondary {
		width: 100%;
	}
}
</style>
