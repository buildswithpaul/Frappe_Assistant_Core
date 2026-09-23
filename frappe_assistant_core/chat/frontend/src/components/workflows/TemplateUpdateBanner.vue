<template>
	<div v-if="update" class="update-banner">
		<div class="update-info">
			<svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
				/>
			</svg>
			<div class="update-text">
				<span class="update-title">Template update available</span>
				<span class="update-version"
					>{{ update.current_version }} &rarr; {{ update.latest_version }}</span
				>
			</div>
		</div>
		<button @click="$emit('dismiss')" class="dismiss-btn" title="Dismiss" aria-label="Dismiss">
			<svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M6 18L18 6M6 6l12 12"
				/>
			</svg>
		</button>
	</div>
</template>

<script setup>
defineProps({
	update: { type: Object, default: null },
});
defineEmits(["dismiss"]);
</script>

<style scoped>
.update-banner {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 0.5rem 1rem;
	background: var(--ql-accent-soft);
	border: 1px solid var(--ql-accent-soft);
	border-radius: 0.5rem;
	margin-bottom: 0.75rem;
}
.update-info {
	display: flex;
	align-items: center;
	gap: 0.625rem;
	color: var(--ql-accent);
}
.update-text {
	display: flex;
	flex-direction: column;
}
.update-title {
	font-size: 0.8125rem;
	font-weight: 600;
	color: var(--ql-text);
}
.update-version {
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
}
.dismiss-btn {
	display: flex;
	padding: 0.25rem;
	background: transparent;
	border: none;
	color: var(--ql-text-muted);
	cursor: pointer;
	border-radius: 0.25rem;
}
.dismiss-btn:hover {
	background: var(--ql-subtle);
	color: var(--ql-text);
}
</style>
