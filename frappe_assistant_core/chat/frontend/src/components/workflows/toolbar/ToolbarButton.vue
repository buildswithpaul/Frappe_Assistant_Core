<template>
	<button class="toolbar-btn"><slot /><span v-if="label" class="btn-label">{{ label }}</span></button>
</template>

<script setup>
// `title`, `aria-label`, `disabled`, extra classes and the click listener all
// reach the button by attribute fallthrough — only the label needs a prop.
defineProps({
	label: { type: String, default: "" },
});
</script>

<style scoped>
.toolbar-btn {
	display: flex;
	align-items: center;
	gap: 0.375rem;
	padding: 0.375rem 0.625rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text);
	background: transparent;
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	cursor: pointer;
	transition: all 0.15s ease;
	white-space: nowrap;
}

.toolbar-btn:hover {
	background: var(--ql-subtle);
}
.toolbar-btn:disabled {
	opacity: 0.5;
	cursor: not-allowed;
}
.toolbar-btn.accent {
	border-color: var(--ql-accent);
	color: var(--ql-accent);
}
.toolbar-btn.active {
	background: var(--ql-subtle);
	border-color: var(--ql-accent);
}

.toolbar-btn.primary {
	color: white;
	background: var(--ql-accent);
	border-color: var(--ql-accent);
}

.toolbar-btn.primary:hover {
	opacity: 0.9;
}
.toolbar-btn.primary:disabled {
	opacity: 0.6;
}

.toolbar-btn.warning {
	color: white;
	background: var(--ql-warning);
	border-color: var(--ql-warning);
}
.toolbar-btn.warning:hover {
	opacity: 0.9;
}
.toolbar-btn.warning:disabled {
	opacity: 0.6;
}

.btn-label {
	display: none;
}
@media (min-width: 768px) {
	.btn-label {
		display: inline;
	}
}
</style>
