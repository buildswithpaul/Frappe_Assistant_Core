<template>
	<div
		class="routing-panel"
		role="region"
		aria-label="Why this model answered"
		tabindex="-1"
		ref="root"
		@keydown.esc="$emit('close')"
	>
		<dl class="routing-rows">
			<div v-for="row in rows" :key="row.key" class="routing-row">
				<dt class="routing-label">{{ row.label }}</dt>
				<dd class="routing-value">
					{{ row.value }}
					<span v-if="row.detail" class="routing-detail">{{ row.detail }}</span>
				</dd>
			</div>
		</dl>
		<p v-for="notice in notices" :key="notice" class="routing-notice">{{ notice }}</p>
		<button type="button" class="routing-close" @click="$emit('close')">Close</button>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { routingRows, NOTICES } from "./routingCopy.js";

const props = defineProps({
	receipt: { type: Object, default: null },
	modelName: { type: String, default: null },
});

defineEmits(["close"]);

const root = ref(null);
const rows = computed(() => routingRows(props.receipt, props.modelName));
const notices = computed(() =>
	(props.receipt?.notices || []).map((code) => NOTICES[code]).filter(Boolean)
);

onMounted(() => root.value?.focus());
</script>

<style scoped>
.routing-panel {
	margin-top: 0.375rem;
	padding: 0.75rem 0.875rem;
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-md);
	background: var(--ql-subtle);
	font-size: 0.75rem;
	max-width: 34rem;
}

.routing-panel:focus-visible {
	outline: 1px solid var(--ql-accent);
	outline-offset: 2px;
}

.routing-rows {
	display: grid;
	gap: 0.5rem;
	margin: 0;
}

.routing-row {
	display: grid;
	grid-template-columns: minmax(8rem, 10rem) 1fr;
	gap: 0.75rem;
	align-items: baseline;
}

.routing-label {
	margin: 0;
	color: var(--ql-text-muted);
}

.routing-value {
	margin: 0;
	color: var(--ql-text);
}

.routing-detail {
	display: block;
	margin-top: 0.125rem;
	color: var(--ql-text-secondary);
}

.routing-notice {
	margin: 0.5rem 0 0;
	color: var(--ql-text-secondary);
}

.routing-close {
	margin-top: 0.625rem;
	padding: 0;
	background: none;
	border: none;
	font: inherit;
	color: var(--ql-accent);
	cursor: pointer;
}

.routing-close:hover {
	color: var(--ql-accent-hover);
}

@media (max-width: 40rem) {
	.routing-row {
		grid-template-columns: 1fr;
		gap: 0.125rem;
	}
}
</style>
