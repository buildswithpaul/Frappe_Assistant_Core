<template>
	<div class="conversations-section">
		<div class="section-header">
			<h3 class="section-title">{{ __("Recents") }}</h3>
			<button
				v-if="showNewChat"
				@click="$emit('new-session')"
				class="new-chat-btn"
				title="New Chat"
				aria-label="New chat"
			>
				<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M12 4v16m8-8H4"
					/>
				</svg>
			</button>
		</div>

		<ConversationSearch
			:model-value="conversations.searchQuery"
			@update:model-value="conversations.setSearch($event)"
		/>

		<div class="conversations-list">
			<!-- Loading State -->
			<div v-if="loading" class="flex items-center justify-center py-8">
				<div
					class="animate-spin w-5 h-5 border-2 border-ql-accent border-t-transparent rounded-full"
				></div>
			</div>

			<!-- Search results -->
			<template v-else-if="isSearchActive">
				<div v-if="conversations.isSearching" class="empty-hint search-status">
					{{ __("Searching…") }}
				</div>
				<div v-else-if="conversations.searchResults.length === 0" class="empty-conversations">
					<p>{{ __("No chats match") }}</p>
				</div>
				<ChatRow
					v-for="session in conversations.searchResults"
					:key="session.session_id"
					:session="session"
					:active="activeSessionId === session.session_id"
					:deleting="deletingSessionId === session.session_id"
					:projects="projectsStore.projects"
					@select="$emit('select-session', session.session_id)"
					@rename="onRename(session.session_id, $event)"
					@move="onMove(session.session_id, $event)"
					@archive="emitDelete(session.session_id)"
					@new-project="$emit('new-project', session.session_id)"
				/>
			</template>

			<!-- Empty State -->
			<div v-else-if="groupedSessions.length === 0" class="empty-conversations">
				<p>{{ __("No conversations yet") }}</p>
				<p class="empty-hint">{{ __("Start a new chat to begin") }}</p>
			</div>

			<!-- Sessions by Date -->
			<template v-else>
				<template v-for="group in groupedSessions" :key="group.label">
					<div class="date-label">{{ group.label }}</div>
					<ChatRow
						v-for="session in group.sessions"
						:key="session.session_id"
						:session="session"
						:active="activeSessionId === session.session_id"
						:deleting="deletingSessionId === session.session_id"
						:projects="projectsStore.projects"
						@select="$emit('select-session', session.session_id)"
						@rename="onRename(session.session_id, $event)"
						@move="onMove(session.session_id, $event)"
						@archive="emitDelete(session.session_id)"
						@new-project="$emit('new-project', session.session_id)"
					/>
				</template>
				<div ref="sentinel" class="list-sentinel" aria-hidden="true"></div>
				<div v-if="chatStore.isLoadingMoreSessions" class="flex items-center justify-center py-2">
					<div
						class="animate-spin w-4 h-4 border-2 border-ql-accent border-t-transparent rounded-full"
					></div>
				</div>
			</template>

			<ArchivedConversations
				:sessions="archivedSessions"
				@load-archived="$emit('load-archived')"
				@continue-archived="$emit('continue-archived', $event)"
			/>
		</div>
	</div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from "vue";
import ChatRow from "./ChatRow.vue";
import ArchivedConversations from "./ArchivedConversations.vue";
import ConversationSearch from "./ConversationSearch.vue";
import { __ } from "@/utils/i18n";
import { useToast } from "@/composables/useToast";
import { useChatStore } from "@/stores/chatStore";
import { useConversationsStore } from "@/stores/conversationsStore";
import { useProjectsStore } from "@/stores/projectsStore";

const SEARCH_MIN_LENGTH = 2;

const props = defineProps({
	sessions: {
		type: Array,
		default: () => [],
	},
	activeSessionId: {
		type: String,
		default: null,
	},
	loading: {
		type: Boolean,
		default: false,
	},
	showNewChat: {
		type: Boolean,
		default: true,
	},
	archivedSessions: {
		type: Array,
		default: () => [],
	},
});

const emit = defineEmits([
	"select-session",
	"new-session",
	"delete-session",
	"continue-archived",
	"load-archived",
	"new-project",
]);

const chatStore = useChatStore();
const conversations = useConversationsStore();
const projectsStore = useProjectsStore();
const { showError } = useToast();

const deletingSessionId = ref(null);
const sentinel = ref(null);
let observer = null;

const isSearchActive = computed(
	() => conversations.searchQuery.trim().length >= SEARCH_MIN_LENGTH
);

function emitDelete(sessionId) {
	deletingSessionId.value = sessionId;
	emit("delete-session", sessionId);
}

function notifyFailure(err) {
	showError(err?.message || __("Something went wrong"));
}

function onRename(sessionId, title) {
	conversations.renameSession(sessionId, title).catch(notifyFailure);
}

function onMove(sessionId, projectId) {
	conversations.moveSession(sessionId, projectId).catch(notifyFailure);
}

// Allow parent to clear deleting state after async operation completes
defineExpose({
	clearDeletingState: () => {
		deletingSessionId.value = null;
	},
});

// IntersectionObserver only reports visibility changes, so a page that leaves the sentinel
// in view would stall paging. Re-observing after each load re-reports the current state.
async function loadMoreIfVisible(entries) {
	if (!entries.some((e) => e.isIntersecting) || !chatStore.sessionsHasMore) return;
	const before = chatStore.sessions.length;
	await chatStore.loadMoreSessions();
	// Only while pages keep arriving, so a failing request cannot loop.
	if (chatStore.sessionsHasMore && chatStore.sessions.length > before) observeSentinel();
}

function observeSentinel() {
	observer?.disconnect();
	if (sentinel.value && typeof IntersectionObserver !== "undefined") {
		observer = new IntersectionObserver(loadMoreIfVisible);
		observer.observe(sentinel.value);
	}
}

// The sentinel is created and destroyed as the list swaps between loading, search and empty.
watch(sentinel, observeSentinel, { flush: "post" });
onBeforeUnmount(() => observer?.disconnect());

// Group sessions by date
const groupedSessions = computed(() => {
	const groups = {};
	const today = new Date();
	today.setHours(0, 0, 0, 0);
	const yesterday = new Date(today);
	yesterday.setDate(yesterday.getDate() - 1);
	const lastWeek = new Date(today);
	lastWeek.setDate(lastWeek.getDate() - 7);

	props.sessions.forEach((session) => {
		// Use last_activity from backend (fallback to modified for backwards compat)
		const dateStr = session.last_activity || session.modified;
		const date = new Date(dateStr);
		date.setHours(0, 0, 0, 0);

		let label;
		if (isNaN(date.getTime())) {
			label = "Recent";
		} else if (date.getTime() === today.getTime()) {
			label = "Today";
		} else if (date.getTime() === yesterday.getTime()) {
			label = "Yesterday";
		} else if (date >= lastWeek) {
			label = "This Week";
		} else {
			label = date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
		}

		if (!groups[label]) {
			groups[label] = [];
		}
		groups[label].push(session);
	});

	return Object.entries(groups).map(([label, sessions]) => ({
		label,
		sessions,
	}));
});
</script>

<style scoped>
.conversations-section {
	flex: 1;
	display: flex;
	flex-direction: column;
	overflow: hidden;
}

.section-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 0.5rem 0.75rem;
	border-bottom: 1px solid var(--ql-border);
}

.section-title {
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.05em;
}

.new-chat-btn {
	padding: 0.25rem;
	color: var(--ql-text-muted);
	border: none;
	background: none;
	border-radius: 0.375rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.new-chat-btn:hover {
	color: var(--ql-text);
	background-color: var(--ql-subtle);
}

.conversations-list {
	flex: 1;
	overflow-y: auto;
	padding: 0.5rem;
}

.date-label {
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	padding: 0.5rem 0.5rem 0.25rem;
	text-transform: uppercase;
	letter-spacing: 0.05em;
}

.search-status {
	text-align: center;
	padding: 1rem;
	color: var(--ql-text-muted);
}

.list-sentinel {
	height: 1px;
}

.empty-conversations {
	text-align: center;
	padding: 2rem 1rem;
	color: var(--ql-text-muted);
}

.empty-conversations p {
	font-size: 0.875rem;
}

.empty-hint {
	font-size: 0.75rem;
	margin-top: 0.25rem;
	opacity: 0.7;
}

/* Scrollbar styling */
.conversations-list::-webkit-scrollbar {
	width: 4px;
}

.conversations-list::-webkit-scrollbar-track {
	background: transparent;
}

.conversations-list::-webkit-scrollbar-thumb {
	background-color: var(--ql-border);
	border-radius: 4px;
}

.conversations-list::-webkit-scrollbar-thumb:hover {
	background-color: var(--ql-text-muted);
}
</style>
