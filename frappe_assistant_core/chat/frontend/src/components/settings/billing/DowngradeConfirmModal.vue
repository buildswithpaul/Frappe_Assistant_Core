<template>
	<Teleport to="body">
		<div v-if="isOpen" class="modal-overlay" @click.self="$emit('cancel')">
			<div class="confirm-modal">
				<div class="confirm-icon-wrap">
					<svg
						class="confirm-icon"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
						/>
					</svg>
				</div>
				<h3 class="confirm-title">Downgrade to Free Plan?</h3>
				<p class="confirm-description">
					Your current plan benefits will remain active until the end of your billing
					period. After that, you'll be moved to the Free plan with limited features and
					credit quota.
				</p>
				<div class="confirm-actions">
					<button
						class="confirm-btn cancel"
						@click="$emit('cancel')"
						:disabled="processing"
					>
						Cancel
					</button>
					<button
						class="confirm-btn confirm"
						@click="$emit('confirm')"
						:disabled="processing"
					>
						{{ processing ? "Processing..." : "Yes, Downgrade" }}
					</button>
				</div>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
defineProps({
	isOpen: { type: Boolean, default: false },
	processing: { type: Boolean, default: false },
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
	z-index: 1100;
	padding: 1rem;
}

.confirm-modal {
	background: var(--ql-surface, #fff);
	border-radius: 0.75rem;
	padding: 1.5rem;
	max-width: 400px;
	width: 100%;
	box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
	text-align: center;
}

.confirm-icon-wrap {
	display: flex;
	justify-content: center;
	margin-bottom: 1rem;
}

.confirm-icon {
	width: 3rem;
	height: 3rem;
	color: #f59e0b;
}

.confirm-title {
	font-size: 1.125rem;
	font-weight: 600;
	color: var(--ql-text);
	margin-bottom: 0.75rem;
}

.confirm-description {
	font-size: 0.875rem;
	color: var(--ql-text-muted);
	line-height: 1.5;
	margin-bottom: 1.5rem;
}

.confirm-actions {
	display: flex;
	gap: 0.75rem;
	justify-content: center;
}

.confirm-btn {
	padding: 0.625rem 1.25rem;
	font-size: 0.875rem;
	font-weight: 500;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
	border: none;
}

.confirm-btn.cancel {
	background: var(--ql-subtle, #f3f4f6);
	color: var(--ql-text);
}

.confirm-btn.cancel:hover:not(:disabled) {
	background: var(--ql-border, #e5e7eb);
}

.confirm-btn.confirm {
	background: #f59e0b;
	color: white;
}

.confirm-btn.confirm:hover:not(:disabled) {
	background: #d97706;
}

.confirm-btn:disabled {
	opacity: 0.6;
	cursor: not-allowed;
}
</style>
