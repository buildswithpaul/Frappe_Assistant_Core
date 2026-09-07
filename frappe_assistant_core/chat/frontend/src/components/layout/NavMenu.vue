<template>
	<nav class="navigation-menu">
		<router-link
			to="/chat"
			class="nav-item"
			:class="{ active: isActiveRoute('/chat') }"
			:title="collapsed ? 'Chat' : ''"
		>
			<svg class="nav-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
				/>
			</svg>
			<span v-if="!collapsed" class="nav-label">Chat</span>
		</router-link>

		<!-- Knowledge Base - only visible when memory app is installed -->
		<router-link
			v-if="memoryEnabled"
			to="/knowledge"
			class="nav-item"
			:class="{ active: isActiveRoute('/knowledge') }"
			:title="collapsed ? 'Knowledge Base' : ''"
		>
			<svg class="nav-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
				/>
			</svg>
			<span v-if="!collapsed" class="nav-label">Knowledge Base</span>
		</router-link>

		<!-- Agents - only visible when workflows app is installed -->
		<router-link
			v-if="workflowsEnabled"
			to="/agents"
			class="nav-item"
			:class="{ active: isActiveRoute('/agents') }"
			:title="collapsed ? 'Agents' : ''"
		>
			<svg class="nav-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M13 10V3L4 14h7v7l9-11h-7z"
				/>
			</svg>
			<span v-if="!collapsed" class="nav-label">Agents</span>
		</router-link>

		<!-- Usage / Analytics - admin only -->
		<router-link
			v-if="isAdmin"
			to="/analytics"
			class="nav-item"
			:class="{ active: isActiveRoute('/analytics') }"
			:title="collapsed ? 'Usage' : ''"
		>
			<svg class="nav-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
				/>
			</svg>
			<span v-if="!collapsed" class="nav-label">Usage</span>
		</router-link>

		<!-- Back to Desk button - continues conversation in widget -->
		<button
			@click="$emit('return-to-desk')"
			class="nav-item back-to-desk"
			:title="collapsed ? 'Back to Desk' : ''"
		>
			<svg class="nav-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"
				/>
			</svg>
			<span v-if="!collapsed" class="nav-label">Back to Desk</span>
		</button>
	</nav>
</template>

<script setup>
import { storeToRefs } from "pinia";
import { useRoute } from "vue-router";
import { useUserStore } from "@/stores/userStore";

defineProps({
	collapsed: {
		type: Boolean,
		default: false,
	},
});

defineEmits(["return-to-desk"]);

const route = useRoute();
const userStore = useUserStore();
const { memoryEnabled, workflowsEnabled, isAdmin } = storeToRefs(userStore);

const isActiveRoute = (path) => {
	return route.path.startsWith(path) || route.path === "/";
};
</script>

<style scoped>
.navigation-menu {
	display: flex;
	flex-direction: column;
	gap: 0.25rem;
	padding: 0.75rem;
}

.nav-item {
	display: flex;
	align-items: center;
	gap: 0.75rem;
	padding: 0.5rem 0.75rem;
	color: var(--ql-text);
	border-radius: 0.5rem;
	text-decoration: none;
	transition: all 0.15s ease;
}

.nav-item:hover {
	background-color: var(--ql-subtle);
}

.nav-item.active {
	background-color: var(--ql-accent-soft);
	color: var(--ql-accent);
}

.nav-icon {
	width: 1.25rem;
	height: 1.25rem;
	flex-shrink: 0;
}

.nav-label {
	font-size: 0.875rem;
	font-weight: 500;
}

.back-to-desk {
	background: none;
	border: none;
	cursor: pointer;
	width: 100%;
	text-align: left;
}
</style>
