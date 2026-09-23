<template>
	<nav v-if="pageCount > 1" class="pager" aria-label="Pagination">
		<button
			class="pager-btn"
			:disabled="page === 0 || disabled"
			@click="$emit('change', page - 1)"
		>
			Previous
		</button>
		<span class="pager-label">Page {{ page + 1 }} of {{ pageCount }}</span>
		<button
			class="pager-btn"
			:disabled="page >= pageCount - 1 || disabled"
			@click="$emit('change', page + 1)"
		>
			Next
		</button>
	</nav>
</template>

<script setup>
defineProps({
	page: { type: Number, default: 0 },
	pageCount: { type: Number, default: 1 },
	disabled: { type: Boolean, default: false },
});

defineEmits(["change"]);
</script>

<style scoped>
.pager {
	display: flex;
	align-items: center;
	justify-content: center;
	gap: 0.75rem;
	padding: 1.25rem 0 0.5rem;
}

.pager-btn {
	padding: 0.375rem 0.875rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text);
	background: transparent;
	border: 1px solid var(--ql-border);
	border-radius: 9999px;
	cursor: pointer;
}

.pager-btn:hover:not(:disabled) {
	border-color: var(--ql-text);
}

.pager-btn:disabled {
	opacity: 0.45;
	cursor: not-allowed;
}

.pager-label {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}
</style>
