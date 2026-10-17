<template>
	<section class="pa">
		<h2 class="pa-label">{{ __("On this page") }}</h2>
		<p class="pa-subject" :title="subject">{{ subject }}</p>
		<div class="pa-chips">
			<button v-for="ask in asks" :key="ask" type="button" class="pa-chip" @click="$emit('pick', ask)">
				{{ ask }}
			</button>
		</div>
	</section>
</template>

<script setup>
import { computed } from "vue";
import { __ } from "@/utils/i18n";

const props = defineProps({
	doctype: { type: String, required: true },
	// Forms only; a list page has no single document.
	name: { type: String, default: "" },
	// Already filled by fillPageAsk.
	asks: { type: Array, default: () => [] },
});
defineEmits(["pick"]);

const subject = computed(() => (props.name ? __("{0} {1}", [props.doctype, props.name]) : props.doctype));
</script>

<style scoped>
.pa {
	padding: var(--ql-space-3);
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-xl);
	min-width: 0;
}
.pa-label {
	margin: 0;
	font-size: var(--ql-label-size); font-weight: 600; text-transform: uppercase;
	letter-spacing: var(--ql-label-tracking); color: var(--ql-text-muted);
}
.pa-subject {
	margin: var(--ql-space-1) 0 var(--ql-space-2);
	font-size: 14px; font-weight: 500; color: var(--ql-text);
	overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.pa-chips { display: flex; flex-wrap: wrap; gap: var(--ql-space-2); }
.pa-chip {
	min-height: 36px; padding: var(--ql-space-1) var(--ql-space-3);
	max-width: 100%; text-align: left; cursor: pointer;
	font-family: var(--ql-font-sans); font-size: 13px; line-height: 1.3; color: var(--ql-accent);
	background: var(--ql-accent-soft); border: 1px solid transparent; border-radius: 999px;
	transition: border-color 0.15s ease;
}
.pa-chip:hover { border-color: var(--ql-accent); }
.pa-chip:focus-visible { outline: 2px solid var(--ql-accent); outline-offset: 2px; }
</style>
