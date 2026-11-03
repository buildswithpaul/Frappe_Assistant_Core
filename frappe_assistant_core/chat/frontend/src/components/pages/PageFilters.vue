<template>
	<div class="page-filters" role="group" :aria-label="__('Show')">
		<button
			v-for="pill in visiblePills"
			:key="pill.key"
			type="button"
			class="page-filter-pill"
			:class="{ 'page-filter-pill--active': pill.key === modelValue }"
			:aria-pressed="pill.key === modelValue ? 'true' : 'false'"
			@click="emit('update:modelValue', pill.key)"
		>
			{{ pill.label }}
		</button>
	</div>
</template>

<script setup>
import { computed } from "vue";

import { __ } from "@/utils/i18n";

const props = defineProps({
	modelValue: { type: String, default: "all" },
	counts: { type: Object, required: true },
});

const emit = defineEmits(["update:modelValue"]);

const visiblePills = computed(() => {
	const pills = [
		{ key: "all", label: __("All {0}", [props.counts.all]) },
		{ key: "mine", label: __("Only you {0}", [props.counts.mine]) },
		{ key: "shared", label: __("Shared {0}", [props.counts.shared]) },
		{ key: "drafts", label: __("Drafts {0}", [props.counts.drafts]) },
	];
	return pills.filter((pill) => pill.key === "all" || props.counts[pill.key] > 0);
});
</script>

<style scoped>
.page-filters {
	display: flex;
	gap: 0.5rem;
	overflow-x: auto;
	padding: 0.125rem;
}

.page-filter-pill {
	flex-shrink: 0;
	padding: 0.3125rem 0.875rem;
	font-size: 0.8125rem;
	border-radius: 999px;
	border: 1px solid var(--ql-border);
	background: var(--ql-surface);
	color: var(--ql-text-secondary);
	cursor: pointer;
}

.page-filter-pill:hover {
	border-color: var(--ql-border-hover);
}

.page-filter-pill:focus-visible {
	outline: none;
	border-color: var(--ql-accent);
	box-shadow: 0 0 0 3px var(--ql-accent-soft);
}

.page-filter-pill--active {
	background: var(--ql-accent);
	border-color: var(--ql-accent);
	color: var(--ql-on-accent, #fff);
}
</style>
