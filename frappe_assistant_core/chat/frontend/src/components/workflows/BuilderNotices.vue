<template>
	<div
		v-if="readOnly || saveError || actionError || validationErrors.length"
		class="builder-notices"
	>
		<div v-if="readOnly" class="notice info">
			<strong>Read-only.</strong> You can open and inspect this agent, but only a System
			Manager can change it.
		</div>

		<div v-if="saveError" class="notice error" role="alert">
			<div class="notice-text">
				<strong>Changes were not saved.</strong> {{ saveError }}
			</div>
			<button class="notice-btn" @click="$emit('retry-save')">Retry</button>
			<button class="notice-btn subtle" @click="$emit('dismiss-error')">Dismiss</button>
		</div>

		<div v-if="actionError" class="notice error" role="alert">
			<div class="notice-text">{{ actionError }}</div>
			<button class="notice-btn subtle" @click="$emit('dismiss-action-error')">
				Dismiss
			</button>
		</div>

		<div v-if="validationErrors.length" class="notice warn">
			<strong
				>{{ validationErrors.length }}
				{{ validationErrors.length === 1 ? "problem" : "problems" }}:</strong
			>
			<ul class="notice-list">
				<li v-for="(err, i) in validationErrors.slice(0, 4)" :key="i">{{ err }}</li>
			</ul>
		</div>
	</div>
</template>

<script setup>
defineProps({
	readOnly: { type: Boolean, default: false },
	saveError: { type: String, default: "" },
	/** A failed action that is not a save — starting a run, saving a schedule. */
	actionError: { type: String, default: "" },
	validationErrors: { type: Array, default: () => [] },
});

defineEmits(["retry-save", "dismiss-error", "dismiss-action-error"]);
</script>

<style scoped>
.builder-notices {
	position: absolute;
	top: 0.75rem;
	left: 50%;
	transform: translateX(-50%);
	z-index: 5;
	width: min(38rem, calc(100% - 2rem));
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
	pointer-events: none;
}

.notice {
	pointer-events: auto;
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.5rem 0.75rem;
	font-size: 0.8125rem;
	line-height: 1.4;
	border-radius: 0.5rem;
	border: 1px solid var(--ql-border);
	background: var(--ql-surface);
	box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
	color: var(--ql-text);
}

.notice-text {
	flex: 1;
	min-width: 0;
}

.notice.info {
	border-color: var(--ql-border);
	color: var(--ql-text-muted);
}

.notice.error {
	border-color: var(--ql-danger);
	color: var(--ql-danger);
}

.notice.warn {
	display: block;
	border-color: var(--ql-warning);
}

.notice-list {
	margin: 0.25rem 0 0;
	padding-left: 1.1rem;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.notice-btn {
	flex-shrink: 0;
	padding: 0.1875rem 0.5rem;
	font-size: 0.75rem;
	font-weight: 600;
	color: inherit;
	background: transparent;
	border: 1px solid currentColor;
	border-radius: 0.25rem;
	cursor: pointer;
}

.notice-btn.subtle {
	border-color: transparent;
	opacity: 0.7;
}

.notice-btn:hover {
	opacity: 1;
}
</style>
