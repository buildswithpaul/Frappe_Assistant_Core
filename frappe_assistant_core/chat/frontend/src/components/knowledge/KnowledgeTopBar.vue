<template>
	<header class="top-bar">
		<div class="top-bar-content">
			<div class="top-bar-left">
				<button
					@click="onHamburger(() => $emit('toggle-sidebar'))"
					class="sidebar-toggle-btn"
					aria-label="Toggle navigation"
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
				<div class="page-title">Knowledge Base</div>
			</div>
			<div class="top-bar-actions">
				<StorageBar v-if="memoryEnabled" :storage="storage" :compact="true" />
				<button
					v-if="memoryEnabled && canUpload"
					@click="$emit('upload')"
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
					<span class="btn-text">Upload</span>
				</button>
			</div>
		</div>
	</header>
</template>

<script setup>
import StorageBar from "./StorageBar.vue";
import { useNavToggle } from "@/composables/useNavToggle";

defineProps({
	memoryEnabled: { type: Boolean, default: false },
	canUpload: { type: Boolean, default: true },
	storage: { type: Object, default: null },
});

defineEmits(["toggle-sidebar", "upload"]);

const { onHamburger } = useNavToggle();
</script>

<style scoped>
.top-bar {
	background: var(--ql-surface);
	border-bottom: 1px solid var(--ql-border);
	height: var(--ql-topbar-height,56px);
	position: sticky;
	top: 0;
	z-index: 20;
}

.top-bar-content {
	height: 100%;
	padding: 0 1rem;
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 1rem;
}

.top-bar-left {
	display: flex;
	align-items: center;
	gap: 0.75rem;
	flex: 1;
	min-width: 0;
}

.top-bar-actions {
	display: flex;
	align-items: center;
	gap: 0.75rem;
}

.sidebar-toggle-btn {
	flex-shrink: 0;
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
	font-size: 1rem;
	font-weight: 600;
	color: var(--ql-text);
}

.action-btn {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.5rem 0.75rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
	background: var(--ql-subtle);
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
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
