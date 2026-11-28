<template>
	<div class="suggested-replies" role="group" :aria-label="__('Suggested replies')">
		<button
			v-for="reply in replies"
			:key="reply"
			type="button"
			class="suggested-reply"
			:disabled="disabled"
			@click="$emit('pick', reply)"
		>
			{{ reply }}
		</button>
	</div>
</template>

<script setup>
import { __ } from "@/utils/i18n";

// Short answers the latest reply offered; a tap sends one as the user's message.
defineProps({
	replies: { type: Array, required: true },
	disabled: { type: Boolean, default: false },
});
defineEmits(["pick"]);
</script>

<style scoped>
.suggested-replies {
	display: flex;
	flex-wrap: wrap;
	gap: 8px;
	margin: 10px 0 2px;
}

.suggested-reply {
	max-width: 100%;
	padding: 6px 12px;
	border: 1px solid var(--ql-border);
	border-radius: 999px;
	background: var(--ql-surface, transparent);
	color: var(--ql-accent);
	font-size: 13px;
	font-weight: 500;
	line-height: 1.35;
	text-align: left;
	cursor: pointer;
	overflow-wrap: anywhere;
	transition:
		background 0.12s ease,
		border-color 0.12s ease;
}

.suggested-reply:hover:not(:disabled) {
	border-color: var(--ql-accent);
	background: var(--ql-accent-soft);
}

.suggested-reply:focus-visible {
	outline: 2px solid var(--ql-accent);
	outline-offset: 2px;
}

.suggested-reply:disabled {
	opacity: 0.55;
	cursor: default;
}
</style>
