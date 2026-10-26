<template>
	<div class="page-write-prompt" role="alertdialog" :aria-label="__('Allow this change?')">
		<svg class="page-write-prompt-icon" viewBox="0 0 24 24" aria-hidden="true">
			<path d="M12 20h9" />
			<path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
		</svg>
		<!-- The description quotes what the page sent: text only, never html. -->
		<p class="page-write-prompt-message">{{ description }}</p>
		<div class="page-write-prompt-buttons">
			<button type="button" class="ql-btn ql-btn-reject" data-test="page-write-deny" @click="emit('decide', false)">
				{{ __("Don't allow") }}
			</button>
			<button type="button" class="ql-btn ql-btn-approve" data-test="page-write-allow" @click="emit('decide', true)">
				{{ __("Allow") }}
			</button>
		</div>
	</div>
</template>

<script setup>
import { __ } from "@/utils/i18n";

defineProps({
	// What the change does, from describePageWrite.
	description: { type: String, required: true },
});

const emit = defineEmits(["decide"]);
</script>

<style src="../interactions/interactionButtons.css"></style>

<style scoped>
.page-write-prompt {
	display: flex;
	align-items: center;
	gap: 10px;
	padding: 10px 16px;
	border-bottom: 1px solid color-mix(in srgb, var(--ql-gold) 45%, var(--ql-border));
	background: color-mix(in srgb, var(--ql-gold) 8%, var(--ql-surface));
}
.page-write-prompt-icon {
	flex: none;
	width: 16px;
	height: 16px;
	fill: none;
	stroke: var(--ql-gold);
	stroke-width: 1.8;
	stroke-linecap: round;
	stroke-linejoin: round;
}
.page-write-prompt-message {
	flex: 1;
	min-width: 0;
	margin: 0;
	font-size: 13px;
	line-height: 1.45;
	color: var(--ql-text);
	overflow-wrap: anywhere;
}
.page-write-prompt-buttons {
	display: flex;
	flex: none;
	gap: 8px;
}

@media (max-width: 767px) {
	.page-write-prompt {
		flex-wrap: wrap;
	}
	.page-write-prompt-buttons {
		width: 100%;
		justify-content: flex-end;
	}
}
</style>
