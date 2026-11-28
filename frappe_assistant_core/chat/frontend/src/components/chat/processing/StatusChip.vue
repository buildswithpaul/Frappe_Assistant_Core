<template>
	<span class="status-chip" :class="`chip-${status}`">
		<svg
			v-if="status === 'running'"
			class="chip-spinner"
			viewBox="0 0 24 24"
			fill="none"
		>
			<circle
				cx="12"
				cy="12"
				r="10"
				stroke="currentColor"
				stroke-width="3"
				opacity="0.25"
			/>
			<path
				d="M12 2a10 10 0 0 1 10 10"
				stroke="currentColor"
				stroke-width="3"
				stroke-linecap="round"
			/>
		</svg>
		<svg
			v-else-if="status === 'error'"
			viewBox="0 0 24 24"
			fill="none"
			stroke="currentColor"
		>
			<path
				stroke-linecap="round"
				stroke-linejoin="round"
				stroke-width="3"
				d="M6 18L18 6M6 6l12 12"
			/>
		</svg>
		<svg
			v-else-if="status === 'stopped'"
			viewBox="0 0 24 24"
			fill="none"
			stroke="currentColor"
		>
			<circle cx="12" cy="12" r="8" stroke-width="3" />
			<path stroke-linecap="round" stroke-width="3" d="M7 17L17 7" />
		</svg>
		<svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor">
			<path
				stroke-linecap="round"
				stroke-linejoin="round"
				stroke-width="3"
				d="M5 13l4 4L19 7"
			/>
		</svg>
	</span>
</template>

<script setup>
defineProps({
	// "running" | "success" | "error" | "stopped" | "cancelled"
	status: { type: String, required: true },
});
</script>

<style scoped>
.status-chip {
	flex-shrink: 0;
	width: 14px;
	height: 14px;
	border-radius: 50%;
	display: inline-flex;
	align-items: center;
	justify-content: center;
	background: color-mix(in srgb, var(--ql-accent) 14%, transparent);
	color: var(--ql-accent);
}

.status-chip svg {
	width: 9px;
	height: 9px;
}

.chip-running {
	background: color-mix(in srgb, var(--ql-warning) 16%, transparent);
	color: var(--ql-warning);
}

.chip-stopped {
	background: color-mix(in srgb, var(--ql-text-muted) 16%, transparent);
	color: var(--ql-text-muted);
}

.chip-error {
	background: color-mix(in srgb, var(--ql-danger) 16%, transparent);
	color: var(--ql-danger);
}

.chip-spinner {
	animation: timeline-spin 1s linear infinite;
}

@keyframes timeline-spin {
	from {
		transform: rotate(0deg);
	}
	to {
		transform: rotate(360deg);
	}
}

@media (prefers-reduced-motion: reduce) {
	.chip-spinner {
		animation: none;
	}
}
</style>
