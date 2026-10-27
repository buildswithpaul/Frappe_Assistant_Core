<template>
	<div class="app-layout">
		<NavigationSidebar @open-settings="router.push('/settings')" />

		<main class="main-content">
			<header class="top-bar">
				<div class="top-bar-content">
					<div class="top-bar-left">
						<button
							v-if="isDrawerWidth"
							type="button"
							class="sidebar-toggle-btn"
							:aria-label="__('Toggle navigation')"
							@click="onHamburger()"
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
						<div class="page-title">{{ title }}</div>
					</div>
					<div class="top-bar-actions"><slot name="actions" /></div>
				</div>
			</header>

			<div class="shell-content"><slot /></div>
		</main>
	</div>
</template>

<script setup>
import { useRouter } from "vue-router";

import NavigationSidebar from "@/components/layout/NavigationSidebar.vue";
import { useNavToggle } from "@/composables/useNavToggle";
import { __ } from "@/utils/i18n";

defineProps({
	title: { type: String, default: "" },
});

const router = useRouter();
const { isDrawerWidth, onHamburger } = useNavToggle();
</script>

<style scoped>
.app-layout {
	display: flex;
	height: 100%;
	min-height: 0;
	overflow: hidden;
}

.main-content {
	flex: 1;
	display: flex;
	flex-direction: column;
	overflow: hidden;
	min-height: 0;
	min-width: 0;
}

.top-bar {
	height: var(--ql-topbar-height, 56px);
	border-bottom: 1px solid var(--ql-border);
	background: var(--ql-surface);
	padding: 0 1.5rem;
	display: flex;
	align-items: center;
	flex-shrink: 0;
}

.top-bar-content {
	display: flex;
	justify-content: space-between;
	align-items: center;
	width: 100%;
}

.top-bar-left {
	display: flex;
	align-items: center;
	gap: 1rem;
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
	font-size: 1.125rem;
	font-weight: 700;
	color: var(--ql-text);
}

.top-bar-actions {
	display: flex;
	gap: 0.5rem;
}

.shell-content {
	flex: 1;
	min-height: 0;
	display: flex;
	flex-direction: column;
	overflow-y: auto;
}
</style>
