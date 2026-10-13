<template>
	<div>
		<button
			v-if="sessions.length > 0 || showArchived"
			class="show-more-btn archived-toggle"
			@click="toggle"
		>
			{{ showArchived ? __("Hide Archived") : __("Archived ({0})", [sessions.length]) }}
		</button>

		<template v-if="showArchived">
			<div class="date-label archived-label">{{ __("Archived") }}</div>
			<div
				v-for="session in sessions"
				:key="'archived-' + session.session_id"
				class="conversation-item archived-item"
			>
				<div class="conversation-content">
					<div class="conversation-title">
						{{ session.preview || __("Archived conversation") }}
					</div>
					<div class="conversation-time">
						{{ formatConversationTime(session.last_activity) }}
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
</template>

<script setup>
import { ref } from "vue";
import { __ } from "@/utils/i18n";
import { formatConversationTime } from "@/utils/formatConversationTime";

defineProps({
	sessions: { type: Array, default: () => [] },
});

const emit = defineEmits(["load-archived", "continue-archived"]);

const showArchived = ref(false);

function toggle() {
	showArchived.value = !showArchived.value;
	if (showArchived.value) emit("load-archived");
}
</script>

<style scoped>
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

.date-label {
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	padding: 0.5rem 0.5rem 0.25rem;
	text-transform: uppercase;
	letter-spacing: 0.05em;
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
</style>
