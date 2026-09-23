<template>
	<div class="conversations-section">
		<div class="section-header">
			<h3 class="section-title">Recent Chats</h3>
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

		<div class="conversations-list">
			<!-- Loading State -->
			<div v-if="loading" class="flex items-center justify-center py-8">
				<div
					class="animate-spin w-5 h-5 border-2 border-ql-accent border-t-transparent rounded-full"
				></div>
			</div>

			<!-- Empty State -->
			<div v-else-if="groupedSessions.length === 0" class="empty-conversations">
				<p>No conversations yet</p>
				<p class="empty-hint">Start a new chat to begin</p>
			</div>

			<!-- Sessions by Date -->
			<template v-else v-for="group in groupedSessions" :key="group.label">
				<div class="date-label">{{ group.label }}</div>
				<div
					v-for="session in group.sessions"
					:key="session.session_id"
					class="conversation-item"
					:class="{
						active: activeSessionId === session.session_id,
						confirming: confirmingDeleteId === session.session_id,
						deleting: deletingSessionId === session.session_id,
					}"
					@click="
						confirmingDeleteId !== session.session_id &&
							$emit('select-session', session.session_id)
					"
				>
					<!-- Delete confirmation state -->
					<template v-if="confirmingDeleteId === session.session_id">
						<div class="confirm-delete">
							<span class="confirm-text">Archive?</span>
							<div class="confirm-actions">
								<button
									class="confirm-btn confirm-yes"
									@click.stop="emitDelete(session.session_id)"
									title="Confirm delete"
									aria-label="Confirm delete"
								>
									<svg
										class="w-3.5 h-3.5"
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											stroke-width="2"
											d="M5 13l4 4L19 7"
										/>
									</svg>
								</button>
								<button
									class="confirm-btn confirm-no"
									@click.stop="confirmingDeleteId = null"
									title="Cancel"
									aria-label="Cancel delete"
								>
									<svg
										class="w-3.5 h-3.5"
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											stroke-width="2"
											d="M6 18L18 6M6 6l12 12"
										/>
									</svg>
								</button>
							</div>
						</div>
					</template>

					<!-- Normal state -->
					<template v-else>
						<div class="conversation-content">
							<div class="conversation-title">
								{{ session.preview || "New conversation" }}
							</div>
							<div class="conversation-time">
								{{ formatTime(session.last_activity || session.modified) }}
							</div>
						</div>
						<button
							v-if="deletingSessionId !== session.session_id"
							class="delete-btn"
							@click.stop="confirmingDeleteId = session.session_id"
							title="Delete conversation"
							aria-label="Delete conversation"
						>
							<svg
								class="w-3.5 h-3.5"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
								/>
							</svg>
						</button>
						<div v-else class="delete-spinner">
							<div
								class="animate-spin w-3.5 h-3.5 border-2 border-red-400 border-t-transparent rounded-full"
							></div>
						</div>
					</template>
				</div>
			</template>

			<button
				v-if="sessions.length > 5"
				@click="showAllSessions = !showAllSessions"
				class="show-more-btn"
			>
				{{ showAllSessions ? "Show Less" : `Show All (${sessions.length})` }}
			</button>

			<!-- Archived toggle -->
			<button
				v-if="archivedSessions.length > 0 || showArchived"
				@click="toggleArchived"
				class="show-more-btn archived-toggle"
			>
				{{ showArchived ? "Hide Archived" : `Archived (${archivedSessions.length})` }}
			</button>

			<!-- Archived sessions -->
			<template v-if="showArchived">
				<div class="date-label archived-label">Archived</div>
				<div
					v-for="session in archivedSessions"
					:key="'archived-' + session.session_id"
					class="conversation-item archived-item"
				>
					<div class="conversation-content">
						<div class="conversation-title">
							{{ session.preview || "Archived conversation" }}
						</div>
						<div class="conversation-time">
							{{ formatTime(session.last_activity) }}
						</div>
					</div>
					<button
						class="continue-btn"
						@click.stop="$emit('continue-archived', session.session_id)"
						title="Continue in new chat"
						aria-label="Continue archived conversation in new chat"
					>
						<svg
							class="w-3.5 h-3.5"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
							/>
						</svg>
					</button>
				</div>
			</template>
		</div>
	</div>
</template>

<script setup>
import { computed, ref } from "vue";

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
]);

const showAllSessions = ref(false);
const showArchived = ref(false);
const confirmingDeleteId = ref(null);
const deletingSessionId = ref(null);

function toggleArchived() {
	showArchived.value = !showArchived.value;
	if (showArchived.value) {
		emit("load-archived");
	}
}

function emitDelete(sessionId) {
	confirmingDeleteId.value = null;
	deletingSessionId.value = sessionId;
	emit("delete-session", sessionId);
}

// Allow parent to clear deleting state after async operation completes
defineExpose({
	clearDeletingState: () => {
		deletingSessionId.value = null;
	},
});

// Group sessions by date
const groupedSessions = computed(() => {
	const displaySessions = showAllSessions.value ? props.sessions : props.sessions.slice(0, 5);
	const groups = {};
	const today = new Date();
	today.setHours(0, 0, 0, 0);
	const yesterday = new Date(today);
	yesterday.setDate(yesterday.getDate() - 1);
	const lastWeek = new Date(today);
	lastWeek.setDate(lastWeek.getDate() - 7);

	displaySessions.forEach((session) => {
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

function formatTime(dateStr) {
	if (!dateStr) return "";
	const date = new Date(dateStr);
	if (isNaN(date.getTime())) return "";
	return date.toLocaleTimeString("en-US", {
		hour: "numeric",
		minute: "2-digit",
		hour12: true,
	});
}
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

.conversation-item {
	padding: 0.5rem 0.75rem;
	border-radius: 0.5rem;
	cursor: pointer;
	margin-bottom: 0.25rem;
	transition: all 0.15s ease;
	display: flex;
	align-items: center;
	gap: 0.25rem;
}

.conversation-item:hover {
	background-color: var(--ql-subtle);
}

.conversation-item.active {
	background-color: var(--ql-accent-soft);
	border-left: 3px solid var(--ql-accent);
}

.conversation-item.confirming {
	background-color: rgba(239, 68, 68, 0.08);
}

.conversation-item.deleting {
	opacity: 0.5;
	pointer-events: none;
}

.conversation-content {
	flex: 1;
	min-width: 0;
}

.conversation-title {
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.conversation-time {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	margin-top: 0.125rem;
}

.delete-btn {
	flex-shrink: 0;
	padding: 0.25rem;
	color: var(--ql-text-muted);
	background: none;
	border: none;
	border-radius: 0.25rem;
	cursor: pointer;
	opacity: 0;
	transition: all 0.15s ease;
}

.conversation-item:hover .delete-btn {
	opacity: 1;
}

.delete-btn:hover {
	color: #ef4444;
	background-color: rgba(239, 68, 68, 0.1);
}

.delete-spinner {
	flex-shrink: 0;
	padding: 0.25rem;
}

.confirm-delete {
	display: flex;
	align-items: center;
	justify-content: space-between;
	width: 100%;
}

.confirm-text {
	font-size: 0.8rem;
	font-weight: 500;
	color: #ef4444;
}

.confirm-actions {
	display: flex;
	gap: 0.25rem;
}

.confirm-btn {
	padding: 0.25rem;
	border: none;
	border-radius: 0.25rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.confirm-yes {
	color: #ef4444;
	background-color: rgba(239, 68, 68, 0.1);
}

.confirm-yes:hover {
	background-color: rgba(239, 68, 68, 0.2);
}

.confirm-no {
	color: var(--ql-text-muted);
	background: none;
}

.confirm-no:hover {
	color: var(--ql-text);
	background-color: var(--ql-subtle);
}

.archived-toggle {
	margin-top: 0.5rem;
	border-top: 1px solid var(--ql-border);
	padding-top: 0.5rem;
}

.archived-label {
	color: var(--ql-text-muted);
	opacity: 0.7;
}

.archived-item {
	opacity: 0.6;
}

.archived-item:hover {
	opacity: 0.9;
}

.continue-btn {
	flex-shrink: 0;
	padding: 0.25rem;
	color: var(--ql-text-muted);
	background: none;
	border: none;
	border-radius: 0.25rem;
	cursor: pointer;
	opacity: 0;
	transition: all 0.15s ease;
}

.archived-item:hover .continue-btn {
	opacity: 1;
}

.continue-btn:hover {
	color: var(--ql-accent);
	background-color: var(--ql-accent-soft);
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

.show-more-btn {
	width: 100%;
	padding: 0.5rem;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	background: none;
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.show-more-btn:hover {
	background-color: var(--ql-subtle);
	color: var(--ql-text);
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
