<template>
	<label class="page-search">
		<span class="page-search-label">{{ __("Search pages") }}</span>
		<svg class="page-search-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
			<circle cx="9" cy="9" r="5.5" />
			<path d="M13.5 13.5 17 17" stroke-linecap="round" />
		</svg>
		<input
			type="search"
			class="page-search-input"
			:value="modelValue"
			:placeholder="__('Search pages')"
			@input="emit('update:modelValue', $event.target.value)"
		/>
	</label>
</template>

<script setup>
import { __ } from "@/utils/i18n";

defineProps({
	modelValue: { type: String, default: "" },
});

const emit = defineEmits(["update:modelValue"]);
</script>

<style scoped>
.page-search {
	position: relative;
	display: block;
	width: 300px;
	max-width: 100%;
}

.page-search-label {
	position: absolute;
	width: 1px;
	height: 1px;
	overflow: hidden;
	clip: rect(0 0 0 0);
	white-space: nowrap;
}

.page-search-icon {
	position: absolute;
	left: 0.625rem;
	top: 50%;
	width: 1rem;
	height: 1rem;
	transform: translateY(-50%);
	color: var(--ql-text-muted);
	pointer-events: none;
}

.page-search-input {
	width: 100%;
	padding: 0.4375rem 0.75rem 0.4375rem 2rem;
	font-size: 0.875rem;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	color: var(--ql-text);
}

.page-search-input:focus-visible {
	outline: 2px solid var(--ql-accent);
	outline-offset: 1px;
}

@media (max-width: 640px) {
	.page-search {
		width: 100%;
	}
}
</style>
