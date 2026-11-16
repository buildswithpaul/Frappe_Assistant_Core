<template>
	<!-- What the user answered FACO's question with, typed or chosen: their own words, as a
	     "You" line where they said it, not only inside FACO's steps (#34546). -->
	<div class="user-answer">
		<div class="user-answer-label">{{ __("You") }}</div>
		<p class="user-answer-text">{{ text }}</p>
	</div>
</template>

<script setup>
import { __ } from "@/utils/i18n";

defineProps({
	text: { type: String, required: true },
});
</script>

<style scoped>
.user-answer {
	margin: 10px 0;
	padding: 6px 0 6px 12px;
	border-left: 2px solid var(--ql-text-muted);
}

.user-answer-label {
	font-size: var(--ql-label-size);
	text-transform: uppercase;
	letter-spacing: var(--ql-label-tracking);
	color: var(--ql-text-muted);
	margin-bottom: 2px;
}

.user-answer-text {
	margin: 0;
	font-size: var(--ql-prompt-size);
	font-weight: 500;
	line-height: 1.5;
	color: var(--ql-text);
	white-space: pre-wrap;
	overflow-wrap: anywhere;
}
</style>
