<template>
	<div class="conversation-search">
		<input
			:value="modelValue"
			type="search"
			class="search-input"
			data-test="conversation-search"
			:placeholder="__('Search chats…')"
			:aria-label="__('Search chats')"
			@input="$emit('update:modelValue', $event.target.value)"
			@keydown.esc="clear"
		/>
		<button
			v-if="modelValue"
			class="clear-btn"
			data-test="search-clear"
			:aria-label="__('Clear search')"
			@click="clear"
		>
			✕
		</button>
	</div>
</template>

<script setup>
import { __ } from "@/utils/i18n";

defineProps({
	modelValue: { type: String, default: "" },
});

const emit = defineEmits(["update:modelValue"]);

function clear() {
	emit("update:modelValue", "");
}
</script>

<style scoped>
.conversation-search {
	position: relative;
	padding: 0.5rem 0.75rem 0;
}

.search-input {
	width: 100%;
	padding: 0.375rem 1.75rem 0.375rem 0.625rem;
	font-size: 0.8rem;
	color: var(--ql-text);
	background: var(--ql-subtle);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	outline: none;
	-webkit-appearance: none;
	appearance: none;
}

.search-input::-webkit-search-cancel-button {
	display: none;
}

.search-input:focus {
	border-color: var(--ql-accent);
}

.clear-btn {
	position: absolute;
	right: 1rem;
	top: calc(50% + 0.25rem);
	transform: translateY(-50%);
	padding: 0.125rem 0.25rem;
	font-size: 0.7rem;
	color: var(--ql-text-muted);
	background: none;
	border: none;
	cursor: pointer;
}

.clear-btn:hover {
	color: var(--ql-text);
}
</style>
