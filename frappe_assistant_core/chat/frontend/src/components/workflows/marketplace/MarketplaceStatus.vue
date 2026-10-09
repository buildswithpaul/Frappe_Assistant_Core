<template>
	<div v-if="loading" class="marketplace-loading">
		<div class="loading-spinner"></div>
		<p>{{ __("Loading templates…") }}</p>
	</div>
	<LoadErrorState v-else-if="error" :message="error" @retry="$emit('retry')" />
	<div v-else-if="empty" class="marketplace-empty">
		<svg
			width="40"
			height="40"
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
			class="empty-icon"
		>
			<path
				stroke-linecap="round"
				stroke-linejoin="round"
				stroke-width="1.5"
				d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
			/>
		</svg>
		<p v-if="filtered">{{ __("No templates match your search.") }}</p>
		<p v-else>{{ __("No templates available yet.") }}</p>
	</div>
</template>

<script setup>
import { __ } from "@/utils/i18n";
import LoadErrorState from "@/components/common/list/LoadErrorState.vue";

defineProps({
	loading: { type: Boolean, default: false },
	error: { type: String, default: "" },
	empty: { type: Boolean, default: false },
	filtered: { type: Boolean, default: false },
});
defineEmits(["retry"]);
</script>

<style scoped>
.marketplace-loading,
.marketplace-empty {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 4rem 1rem;
	color: var(--ql-text-muted);
	font-size: 0.8125rem;
}

.empty-icon {
	margin-bottom: 1rem;
	opacity: 0.4;
}

.loading-spinner {
	width: 1.5rem;
	height: 1.5rem;
	border: 2px solid var(--ql-border);
	border-top-color: var(--ql-accent);
	border-radius: 50%;
	animation: spin 0.8s linear infinite;
	margin-bottom: 0.75rem;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}
</style>
