<template>
	<div
		class="save-bar"
		:class="{ 'is-error': !!error, 'is-saved': isSaved }"
		role="status"
		aria-live="polite"
	>
		<span class="save-status">
			<span class="save-dot" aria-hidden="true"></span>
			{{ statusText }}
		</span>
		<template v-if="dirty || saving">
			<button class="discard-btn" :disabled="saving" @click="$emit('discard')">
				Discard
			</button>
			<button class="save-btn" :disabled="saving || !dirty" @click="$emit('save')">
				{{ saving ? "Saving…" : "Save" }}
			</button>
		</template>
	</div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
	dirty: { type: Boolean, default: false },
	saving: { type: Boolean, default: false },
	error: { type: String, default: null },
	successMessage: { type: String, default: null },
});

defineEmits(["save", "discard"]);

const isSaved = computed(() => !!props.successMessage && !props.dirty && !props.error);

const statusText = computed(() => {
	if (props.error) return props.error;
	if (isSaved.value) return props.successMessage;
	return "Unsaved changes";
});
</script>

<style scoped>
/* Sticks to the bottom of the settings scrollport so the commit is always one
   click away, whatever the scroll position. */
.save-bar {
	position: sticky;
	bottom: 0;
	z-index: 5;
	display: flex;
	align-items: center;
	gap: 0.75rem;
	padding: 12px 16px;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 12px;
	box-shadow: 0 6px 20px rgba(0, 0, 0, 0.1);
}

.save-status {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	flex: 1;
	min-width: 0;
	font-size: 0.8rem;
	color: var(--ql-text-secondary);
}

.save-dot {
	flex-shrink: 0;
	width: 7px;
	height: 7px;
	border-radius: 50%;
	background: var(--ql-warning);
}

.save-bar.is-saved .save-dot {
	background: var(--ql-success);
}

.save-bar.is-saved .save-status {
	color: var(--ql-success);
}

.save-bar.is-error {
	border-color: rgba(239, 68, 68, 0.35);
}

.save-bar.is-error .save-dot {
	background: var(--ql-danger);
}

.save-bar.is-error .save-status {
	color: var(--ql-danger);
}

.save-btn,
.discard-btn {
	flex-shrink: 0;
	padding: 0.5rem 1.25rem;
	font-size: 0.85rem;
	font-weight: 500;
	border-radius: 0.375rem;
	cursor: pointer;
	transition: opacity 0.15s ease, background-color 0.15s ease;
}

.save-btn {
	color: white;
	background: var(--ql-accent);
	border: none;
}

.discard-btn {
	color: var(--ql-text-secondary);
	background: transparent;
	border: 1px solid var(--ql-border);
}

.save-btn:hover:not(:disabled) {
	opacity: 0.9;
}

.discard-btn:hover:not(:disabled) {
	background: var(--ql-bg);
	color: var(--ql-text);
}

.save-btn:disabled,
.discard-btn:disabled {
	opacity: 0.4;
	cursor: not-allowed;
}

@media (max-width: 480px) {
	.save-bar {
		flex-wrap: wrap;
	}
	.save-status {
		flex-basis: 100%;
	}
}
</style>
