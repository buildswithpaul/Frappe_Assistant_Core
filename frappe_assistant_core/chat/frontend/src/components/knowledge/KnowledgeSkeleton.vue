<template>
	<div class="documents-grid">
		<div v-for="n in 6" :key="n" class="skeleton-card">
			<div class="skeleton-accent"></div>
			<div class="skeleton-inner">
				<div class="skeleton-header">
					<div class="skeleton-badge"></div>
					<div class="skeleton-pill"></div>
				</div>
				<div class="skeleton-name"></div>
				<div class="skeleton-footer"></div>
			</div>
		</div>
	</div>
</template>

<script setup></script>

<style scoped>
.documents-grid {
	display: grid;
	grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
	gap: 0.75rem;
}

.skeleton-card {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	overflow: hidden;
}

.skeleton-accent {
	height: 3px;
	background: var(--ql-border);
	animation: skeleton-pulse 1.5s ease-in-out infinite;
}

.skeleton-inner {
	padding: 0.75rem 1rem;
}

.skeleton-header {
	display: flex;
	gap: 0.5rem;
	margin-bottom: 0.625rem;
}

.skeleton-badge {
	width: 36px;
	height: 18px;
	background: var(--ql-border);
	border-radius: 0.25rem;
	animation: skeleton-pulse 1.5s ease-in-out infinite;
}

.skeleton-pill {
	width: 56px;
	height: 18px;
	background: var(--ql-border);
	border-radius: 9999px;
	animation: skeleton-pulse 1.5s ease-in-out infinite 0.1s;
}

.skeleton-name {
	height: 16px;
	background: var(--ql-border);
	border-radius: 0.25rem;
	width: 70%;
	margin-bottom: 0.625rem;
	animation: skeleton-pulse 1.5s ease-in-out infinite 0.2s;
}

.skeleton-footer {
	height: 12px;
	width: 50%;
	background: var(--ql-border);
	border-radius: 0.25rem;
	animation: skeleton-pulse 1.5s ease-in-out infinite 0.3s;
}

@keyframes skeleton-pulse {
	0%,
	100% {
		opacity: 0.3;
	}
	50% {
		opacity: 0.7;
	}
}

@media (max-width: 768px) {
	.documents-grid {
		grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
		gap: 0.75rem;
	}
}
</style>
