<template>
	<div class="load-error" role="alert">
		<p class="load-error-title">{{ __("Couldn't load this") }}</p>
		<p class="load-error-text">{{ message }}</p>
		<button type="button" class="load-error-btn" @click="$emit('retry')">
			{{ __("Retry") }}
		</button>
	</div>
</template>

<script setup>
import { __ } from "@/utils/i18n";

defineProps({ message: { type: String, required: true } });
defineEmits(["retry"]);
</script>

<style scoped>
.load-error {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: var(--ql-space-2);
	padding: var(--ql-space-8) var(--ql-space-4);
	text-align: center;
	color: var(--ql-text);
	background: color-mix(in srgb, var(--ql-danger) 6%, transparent);
	border: 1px solid color-mix(in srgb, var(--ql-danger) 30%, transparent);
	border-radius: var(--ql-radius-lg);
}
.load-error-title {
	font-weight: 600;
	margin: 0;
}
.load-error-text {
	font-size: 0.875rem;
	color: var(--ql-text-muted);
	max-width: 32rem;
	margin: 0;
}
.load-error-btn {
	padding: 0.375rem 0.875rem;
	font-size: 0.8125rem;
	color: var(--ql-accent);
	background: transparent;
	border: 1px solid var(--ql-accent);
	border-radius: var(--ql-radius-sm);
	cursor: pointer;
}
.load-error-btn:hover {
	background: var(--ql-accent-soft);
}
</style>
