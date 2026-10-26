<template>
	<div class="pwp" role="alertdialog" aria-modal="false" :aria-label="__('Allow this?')">
		<div class="pwp-head">
			<svg class="pwp-icon" viewBox="0 0 24 24" aria-hidden="true">
				<path d="M12 20h9" />
				<path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
			</svg>
			<!-- Everything here quotes what the page sent: text only, never html. -->
			<p class="pwp-message page-write-prompt-message">{{ request.message }}</p>
			<span v-if="total > 1" class="pwp-count" data-test="page-write-count">
				{{ __("{0} of {1}", [1, total]) }}
			</span>
		</div>
		<p v-if="request.hiddenChars" class="pwp-warning" data-test="page-write-hidden">
			{{ __("This request contained hidden characters, which are left out below.") }}
		</p>
		<dl v-if="request.fields.length" class="pwp-fields page-write-prompt-fields">
			<PageWriteField v-for="(field, i) in request.fields" :key="i" :field="field" />
		</dl>
		<p v-if="request.note" class="pwp-note">{{ request.note }}</p>
		<div class="pwp-buttons">
			<button type="button" class="ql-btn ql-btn-reject" data-test="page-write-deny" @click="emit('decide', false)">
				{{ __("Don't allow") }}
			</button>
			<button
				v-if="request.trustable"
				type="button"
				class="ql-btn ql-btn-reject"
				data-test="page-write-trust"
				:disabled="!armed"
				@click="emit('decide', 'page')"
			>
				{{ __("Allow for this page") }}
			</button>
			<button
				type="button"
				class="ql-btn ql-btn-approve"
				data-test="page-write-allow"
				:disabled="!armed"
				@click="emit('decide', 'once')"
			>
				{{ request.trustable ? __("Allow once") : __("Allow") }}
			</button>
		</div>
	</div>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from "vue";

import { __ } from "@/utils/i18n";

import PageWriteField from "./PageWriteField.vue";

const props = defineProps({
	// From describePageRequest: {message, note, fields, trustable, hiddenChars}.
	request: { type: Object, required: true },
	// How many prompts are waiting, this one included.
	total: { type: Number, default: 1 },
});

// "once", "page" or false.
const emit = defineEmits(["decide"]);

// How long the allow buttons stay off after a prompt appears or changes, so a click aimed at the
// page cannot land on one.
const ARM_DELAY_MS = 700;

const armed = ref(false);
let timer = null;
watch(
	() => props.request,
	() => {
		armed.value = false;
		clearTimeout(timer);
		timer = setTimeout(() => (armed.value = true), ARM_DELAY_MS);
	},
	{ immediate: true },
);
onBeforeUnmount(() => clearTimeout(timer));
</script>

<style src="../interactions/interactionButtons.css"></style>

<style scoped>
/* Pinned over the top of the page, so the page under it never moves. */
.pwp {
	position: absolute;
	top: 8px;
	left: 8px;
	right: 8px;
	z-index: 5;
	display: flex;
	flex-direction: column;
	gap: 8px;
	max-height: min(70%, 520px);
	padding: 12px 14px;
	border: 1px solid color-mix(in srgb, var(--ql-gold) 45%, var(--ql-border));
	border-radius: var(--ql-radius-lg);
	background: var(--ql-surface);
	box-shadow: 0 8px 24px rgba(26, 26, 23, 0.16);
}
.pwp-head {
	display: flex;
	align-items: flex-start;
	gap: 10px;
}
.pwp-icon {
	flex: none;
	width: 16px;
	height: 16px;
	margin-top: 2px;
	fill: none;
	stroke: var(--ql-gold);
	stroke-width: 1.8;
	stroke-linecap: round;
	stroke-linejoin: round;
}
.pwp-message {
	flex: 1;
	min-width: 0;
	margin: 0;
	font-size: 13px;
	line-height: 1.45;
	color: var(--ql-text);
	overflow-wrap: anywhere;
}
.pwp-count {
	flex: none;
	font-size: 12px;
	color: var(--ql-text-muted);
}
.pwp-warning {
	margin: 0;
	font-size: 12px;
	font-weight: 600;
	color: var(--ql-danger);
}
.pwp-fields {
	display: grid;
	grid-template-columns: max-content 1fr;
	gap: 3px 12px;
	min-height: 0;
	margin: 0;
	padding: 8px 10px;
	overflow: auto;
	border-radius: var(--ql-radius-md);
	background: var(--ql-subtle);
	font-size: 12px;
	line-height: 1.45;
}
.pwp-note {
	margin: 0;
	font-size: 12px;
	color: var(--ql-text-secondary);
}
.pwp-buttons {
	display: flex;
	flex-wrap: wrap;
	justify-content: flex-end;
	gap: 8px;
}
</style>
