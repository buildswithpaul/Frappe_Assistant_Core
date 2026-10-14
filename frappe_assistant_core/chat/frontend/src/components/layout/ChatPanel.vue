<template>
	<section class="chat-panel" :aria-label="__('Chats')">
		<button
			v-if="showNewChat"
			type="button"
			class="new-chat-btn"
			data-test="new-chat"
			@click="$emit('new-chat')"
		>
			<svg class="new-chat-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
			</svg>
			{{ __("New chat") }}
		</button>

		<ConversationSearch
			class="panel-search"
			:model-value="conversationsStore.searchQuery"
			@update:model-value="conversationsStore.setSearch($event)"
		/>

		<ProjectsSection ref="projectsSectionRef" />

		<ConversationsList
			:sessions="sessions"
			:archived-sessions="archivedSessions"
			:active-session-id="activeSessionId"
			:loading="loading"
			@select-session="$emit('session-selected', $event)"
			@delete-session="$emit('delete-session', $event)"
			@continue-archived="$emit('continue-archived', $event)"
			@load-archived="$emit('load-archived')"
			@new-project="createProjectFor"
		/>
	</section>
</template>

<script setup>
import { ref } from "vue";
import ProjectsSection from "./ProjectsSection.vue";
import ConversationSearch from "./ConversationSearch.vue";
import ConversationsList from "./ConversationsList.vue";
import { useConversationsStore } from "@/stores/conversationsStore";
import { __ } from "@/utils/i18n";

defineProps({
	sessions: { type: Array, default: () => [] },
	archivedSessions: { type: Array, default: () => [] },
	activeSessionId: { type: String, default: null },
	loading: { type: Boolean, default: false },
	showNewChat: { type: Boolean, default: false },
});

defineEmits(["session-selected", "new-chat", "delete-session", "continue-archived", "load-archived"]);

const conversationsStore = useConversationsStore();
const projectsSectionRef = ref(null);

function createProjectFor(sessionId) {
	projectsSectionRef.value?.startCreate({ moveSessionId: sessionId });
}
</script>

<style scoped>
.chat-panel {
	display: flex;
	flex-direction: column;
	width: var(--ql-panel-width, 240px);
	flex-shrink: 0;
	min-height: 0;
	height: 100%;
	background-color: var(--ql-surface);
	border-right: 1px solid var(--ql-border);
	padding-top: 0.75rem;
	box-sizing: border-box;
}

.new-chat-btn {
	display: flex;
	align-items: center;
	justify-content: center;
	gap: 0.5rem;
	margin: 0 0.75rem 0.5rem;
	min-height: 2.25rem;
	padding: 0.5rem 0.75rem;
	border: none;
	border-radius: 0.5rem;
	background-color: var(--ql-accent);
	color: #fff;
	font-size: 0.875rem;
	font-weight: 600;
	cursor: pointer;
	transition: filter 0.15s ease;
}

.new-chat-btn:hover {
	filter: brightness(1.08);
}

.new-chat-icon {
	width: 1rem;
	height: 1rem;
}

.panel-search {
	padding-bottom: 0.25rem;
}
</style>
