<template>
	<div class="app-layout">
		<!-- Navigation Sidebar -->
		<NavigationSidebar @open-settings="router.push('/settings')" />

		<!-- Main Content Area -->
		<main class="main-content">
			<!-- Top Bar -->
			<header class="top-bar">
				<div class="top-bar-content">
					<div class="top-bar-left">
						<button
							v-if="isDrawerWidth"
							@click="onHamburger()"
							class="sidebar-toggle-btn"
							aria-label="Toggle navigation"
						>
							<svg
								class="w-5 h-5"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M4 6h16M4 12h16M4 18h16"
								/>
							</svg>
						</button>
						<div class="page-title">Usage</div>
					</div>
					<div class="top-bar-actions" v-if="!drilling">
						<div class="range-selector">
							<button
								v-for="r in ranges"
								:key="r"
								class="range-btn"
								:class="{ active: range === r }"
								@click="range = r"
							>
								{{ r }}D
							</button>
						</div>
					</div>
				</div>
			</header>

			<!-- Content. Members reach this route too; until MyUsage lands they get nothing, never the
			     workspace view. -->
			<div class="analytics-content">
				<WorkspaceUsage v-if="userStore.isAdmin" :range="range" @drilling="drilling = $event" />
			</div>
		</main>
	</div>
</template>

<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import NavigationSidebar from "@/components/layout/NavigationSidebar.vue";
import WorkspaceUsage from "@/components/analytics/usage/WorkspaceUsage.vue";
import { useUserStore } from "@/stores/userStore";
import { useNavToggle } from "@/composables/useNavToggle";

const router = useRouter();
const userStore = useUserStore();
const { isDrawerWidth, onHamburger } = useNavToggle();

const ranges = [7, 30, 90];
const range = ref(30);
const drilling = ref(false);
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

/* Date Range Selector */
.range-selector {
	display: flex;
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	overflow: hidden;
}

.range-btn {
	padding: 0.375rem 0.75rem;
	font-size: 0.8rem;
	font-weight: 600;
	color: var(--ql-text-secondary);
	background: transparent;
	border: none;
	cursor: pointer;
	transition: all 0.15s ease;
}

.range-btn:hover {
	color: var(--ql-text);
	background: var(--ql-subtle);
}

.range-btn.active {
	color: white;
	background: var(--ql-accent);
}

/* Analytics Content */
.analytics-content {
	flex: 1;
	overflow-y: auto;
	padding: 1.5rem;
}

@media (max-width: 768px) {
	.analytics-content {
		padding: 1rem;
	}
}
</style>
