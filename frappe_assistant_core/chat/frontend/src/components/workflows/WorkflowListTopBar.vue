<template>
	<header class="top-bar">
		<div class="top-bar-content">
			<div class="top-bar-left">
				<button
					@click="onHamburger(() => $emit('toggle-sidebar'))"
					class="sidebar-toggle-btn"
					aria-label="Toggle sidebar"
				>
					<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M4 6h16M4 12h16M4 18h16"
						/>
					</svg>
				</button>
				<h1 class="page-title">Agents</h1>
			</div>
			<div class="top-bar-actions">
				<button
					v-if="userPublishingEnabled"
					@click="$emit('upload-template')"
					class="action-btn"
					title="Upload Template"
				>
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
						/>
					</svg>
					<span class="btn-text">Upload Template</span>
				</button>
				<button
					v-if="isAdmin"
					@click="$emit('create-workflow')"
					class="action-btn primary"
				>
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M12 4v16m8-8H4"
						/>
					</svg>
					<span class="btn-text">New Agent</span>
				</button>
			</div>
		</div>
	</header>
</template>

<script setup>
import { useNavToggle } from "@/composables/useNavToggle";

defineProps({
	isAdmin: { type: Boolean, default: false },
	// Marketplace publishing kill switch — when off, only platform admins
	// see the Upload Template button. Source: userStore.userPublishingEnabled.
	userPublishingEnabled: { type: Boolean, default: false },
});

defineEmits(["toggle-sidebar", "upload-template", "create-workflow"]);

const { onHamburger } = useNavToggle();
</script>

<style scoped>
.top-bar {
	background: var(--ql-surface);
	border-bottom: 1px solid var(--ql-border);
	height: var(--ql-topbar-height, 56px);
	flex-shrink: 0;
}

.top-bar-content {
	height: 100%;
	padding: 0 1.5rem;
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 1rem;
}

.top-bar-left {
	display: flex;
	align-items: center;
	gap: 0.75rem;
}

.top-bar-actions {
	display: flex;
	align-items: center;
	gap: 0.5rem;
}

.sidebar-toggle-btn {
	padding: 0.5rem;
	color: var(--ql-text-muted);
	background: transparent;
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.sidebar-toggle-btn:hover {
	background-color: var(--ql-subtle);
	color: var(--ql-text);
}

.page-title {
	font-size: 1.125rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0;
}

.action-btn {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.5rem 0.875rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
	background: var(--ql-subtle);
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.action-btn:hover {
	background-color: var(--ql-border);
}
.action-btn.primary {
	color: white;
	background-color: var(--ql-accent);
}
.action-btn.primary:hover {
	background-color: var(--ql-accent-hover);
}

.btn-text {
	display: none;
}
@media (min-width: 640px) {
	.btn-text {
		display: inline;
	}
}

.w-4 {
	width: 1rem;
	height: 1rem;
}
.w-5 {
	width: 1.25rem;
	height: 1.25rem;
}
</style>
