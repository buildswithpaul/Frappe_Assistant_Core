<template>
	<!-- Not Available State -->
	<div v-if="status === 'unavailable'" class="kb-unavailable">
		<svg class="unavailable-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<path
				stroke-linecap="round"
				stroke-linejoin="round"
				stroke-width="1.5"
				d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
			/>
		</svg>
		<h3>Knowledge Base Not Available</h3>
		<p>The Knowledge Base feature requires the memory module to be installed.</p>
	</div>

	<!-- Error State -->
	<div v-else-if="status === 'error'" class="kb-error">
		<svg class="error-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<path
				stroke-linecap="round"
				stroke-linejoin="round"
				stroke-width="2"
				d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
			/>
		</svg>
		<p>{{ error }}</p>
		<button class="retry-btn" @click="$emit('retry')">Retry</button>
	</div>

	<!-- Drag Overlay -->
	<div v-else-if="status === 'dragging'" class="drag-overlay">
		<div class="drag-overlay-content">
			<svg class="drag-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
				/>
			</svg>
			<p class="drag-text">Drop files to upload</p>
			<p class="drag-hint">PDF, Markdown, or Text files</p>
		</div>
	</div>
</template>

<script setup>
defineProps({
	status: { type: String, required: true }, // 'unavailable' | 'error' | 'dragging'
	error: { type: String, default: "" },
});

defineEmits(["retry"]);
</script>

<style scoped>
/* Unavailable State */
.kb-unavailable {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	text-align: center;
	padding: 4rem 2rem;
	gap: 1rem;
}

.unavailable-icon {
	width: 3rem;
	height: 3rem;
	color: var(--ql-text-muted);
}
.kb-unavailable h3 {
	font-size: 1.125rem;
	font-weight: 600;
	color: var(--ql-text);
}
.kb-unavailable p {
	font-size: 0.875rem;
	color: var(--ql-text-secondary);
	max-width: 400px;
}

/* Error State */
.kb-error {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 4rem 2rem;
	gap: 1rem;
	text-align: center;
}

.error-icon {
	width: 2.5rem;
	height: 2.5rem;
	color: var(--ql-danger);
}
.kb-error p {
	font-size: 0.875rem;
	color: var(--ql-text-secondary);
}

.retry-btn {
	padding: 0.5rem 1rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-accent);
	background: none;
	border: 1px solid var(--ql-accent);
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.retry-btn:hover {
	background-color: var(--ql-accent-soft);
}

/* Drag Overlay */
.drag-overlay {
	position: absolute;
	inset: 0;
	z-index: 30;
	display: flex;
	align-items: center;
	justify-content: center;
	background: var(--ql-accent-soft);
	border: 2px dashed var(--ql-accent);
	border-radius: 0.75rem;
	margin: 0.5rem;
	backdrop-filter: blur(2px);
	animation: drag-pulse 1.5s ease-in-out infinite;
}

@keyframes drag-pulse {
	0%,
	100% {
		background: var(--ql-accent-soft);
	}
	50% {
		background: var(--ql-accent-soft);
	}
}

.drag-overlay-content {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 0.5rem;
}

.drag-icon {
	width: 2.5rem;
	height: 2.5rem;
	color: var(--ql-accent);
}
.drag-text {
	font-size: 1rem;
	font-weight: 600;
	color: var(--ql-accent);
}
.drag-hint {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}
</style>
