<template>
	<div class="status-bar">
		<span class="status-item">
			{{ nodeCount }} node{{ nodeCount !== 1 ? "s" : "" }}
			&middot;
			{{ edgeCount }} edge{{ edgeCount !== 1 ? "s" : "" }}
		</span>
		<span v-if="validationMessage" class="status-item" :class="validationClass">
			{{ validationMessage }}
		</span>
		<span class="status-spacer"></span>
		<span v-if="saveError" class="status-item status-error" :title="saveError"
			>Save failed</span
		>
		<span v-else-if="isDirty" class="status-item status-dirty">Unsaved changes</span>
		<span v-else-if="hasSaved" class="status-item status-saved">All changes saved</span>
	</div>
</template>

<script setup>
defineProps({
	nodeCount: { type: Number, default: 0 },
	edgeCount: { type: Number, default: 0 },
	validationMessage: { type: String, default: "" },
	validationClass: { type: String, default: "" },
	saveError: { type: String, default: null },
	isDirty: { type: Boolean, default: false },
	hasSaved: { type: Boolean, default: false },
});
</script>

<style scoped>
.status-bar {
	display: flex;
	align-items: center;
	gap: 1rem;
	padding: 0 1rem;
	height: 1.75rem;
	background: var(--ql-surface);
	border-top: 1px solid var(--ql-border);
	flex-shrink: 0;
}

.status-item {
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
}

.status-spacer {
	flex: 1;
}
.status-dirty {
	color: var(--ql-warning);
}
.status-saved {
	color: var(--ql-success);
}
.status-valid {
	color: var(--ql-success);
}
.status-error {
	color: var(--ql-danger);
}
</style>
