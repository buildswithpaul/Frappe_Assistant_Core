<template>
	<nav class="nav-rail" :aria-label="__('Main')">
		<router-link to="/chat" class="rail-logo" :aria-label="__('FACO home')" :title="__('FACO')">
			<FacoRobot size="sm" show-arms />
		</router-link>

		<div class="rail-group">
			<router-link v-slot="{ href, navigate }" to="/chat" custom>
				<a
					:href="href"
					class="rail-item"
					:class="{ active: isChatRoute }"
					data-test="rail-chat"
					:aria-label="__('Chat')"
					:title="__('Chat')"
					@click="onChatClick($event, navigate)"
				>
					<svg class="rail-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
						/>
					</svg>
				</a>
			</router-link>

			<router-link
				v-if="memoryEnabled"
				to="/knowledge"
				class="rail-item"
				:class="{ active: route.path.startsWith('/knowledge') }"
				data-test="rail-knowledge"
				:aria-label="__('Knowledge Base')"
				:title="__('Knowledge Base')"
			>
				<svg class="rail-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
					/>
				</svg>
			</router-link>

			<router-link
				v-if="workflowsEnabled"
				to="/agents"
				class="rail-item"
				:class="{ active: route.path.startsWith('/agents') }"
				data-test="rail-agents"
				:aria-label="__('Agents')"
				:title="__('Agents')"
			>
				<svg class="rail-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
				</svg>
			</router-link>

			<router-link
				v-if="isAdmin"
				to="/analytics"
				class="rail-item"
				:class="{ active: route.path.startsWith('/analytics') }"
				data-test="rail-usage"
				:aria-label="__('Usage')"
				:title="__('Usage')"
			>
				<svg class="rail-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
					/>
				</svg>
			</router-link>
		</div>

		<div class="rail-group rail-bottom">
			<button
				type="button"
				class="rail-item"
				data-test="rail-desk"
				:aria-label="__('Back to Desk')"
				:title="__('Back to Desk')"
				@click="$emit('return-to-desk')"
			>
				<svg class="rail-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"
					/>
				</svg>
			</button>
			<UserDropdown @open-settings="$emit('open-settings')" />
		</div>
	</nav>
</template>

<script setup>
import { computed } from "vue";
import { storeToRefs } from "pinia";
import { useRoute } from "vue-router";
import { useUserStore } from "@/stores/userStore";
import { __ } from "@/utils/i18n";
import FacoRobot from "@/components/common/FacoRobot.vue";
import UserDropdown from "./UserDropdown.vue";

const props = defineProps({
	panelCollapsed: { type: Boolean, default: false },
});

const emit = defineEmits(["return-to-desk", "open-settings", "toggle-sidebar"]);

const route = useRoute();
const { memoryEnabled, workflowsEnabled, isAdmin } = storeToRefs(useUserStore());

const isChatRoute = computed(() => route.path.startsWith("/chat") || route.path === "/");

// On a chat route with the panel collapsed, Chat only reopens the panel: navigating to
// /chat would drop the open chat or project page.
function onChatClick(event, navigate) {
	if (props.panelCollapsed && isChatRoute.value) {
		event.preventDefault();
		emit("toggle-sidebar");
		return;
	}
	navigate(event);
}
</script>

<style scoped>
.nav-rail {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 0.75rem;
	width: var(--ql-rail-width, 52px);
	flex-shrink: 0;
	padding: 0.75rem 0;
	background-color: var(--ql-surface);
	border-right: 1px solid var(--ql-border);
	height: 100%;
	box-sizing: border-box;
}

.rail-logo {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 2.25rem;
	height: 2.25rem;
}

.rail-group {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 0.25rem;
}

.rail-bottom {
	margin-top: auto;
	gap: 0.5rem;
}

.rail-item {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 2.25rem;
	height: 2.25rem;
	border-radius: 0.5rem;
	color: var(--ql-text-muted);
	background: none;
	border: none;
	cursor: pointer;
	text-decoration: none;
	transition: background-color 0.15s ease, color 0.15s ease;
}

.rail-item:hover {
	background-color: var(--ql-subtle);
	color: var(--ql-text);
}

.rail-item.active {
	background-color: var(--ql-accent-soft);
	color: var(--ql-accent);
}

.rail-icon {
	width: 1.25rem;
	height: 1.25rem;
}
</style>
