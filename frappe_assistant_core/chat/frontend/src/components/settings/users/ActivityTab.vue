<template>
	<div class="activity-tab">
		<!-- Header: count + event-type filter -->
		<div class="activity-header">
			<span class="activity-count">
				{{ filtered.length }}
				{{ filtered.length === 1 ? "event" : "events" }}
			</span>
			<label class="filter">
				<span class="filter-label">Event</span>
				<select v-model="eventFilter" class="filter-select">
					<option value="">All events</option>
					<option v-for="a in ACTIONS" :key="a" :value="a">{{ a }}</option>
				</select>
			</label>
		</div>

		<!-- Loading state -->
		<div v-if="loading && entries.length === 0" class="loading-state">
			<svg class="spinner" viewBox="0 0 24 24">
				<circle
					cx="12"
					cy="12"
					r="10"
					stroke="currentColor"
					stroke-width="3"
					fill="none"
					opacity="0.25"
				/>
				<path
					d="M12 2a10 10 0 0 1 10 10"
					stroke="currentColor"
					stroke-width="3"
					fill="none"
					stroke-linecap="round"
				/>
			</svg>
			<span>Loading activity...</span>
		</div>

		<!-- Empty state -->
		<div v-else-if="filtered.length === 0" class="empty-state">
			<div class="empty-icon">
				<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
					/>
				</svg>
			</div>
			<p>{{ eventFilter ? "No matching activity." : "No recent activity." }}</p>
		</div>

		<!-- Chronological feed -->
		<ul v-else class="feed">
			<li v-for="(entry, i) in filtered" :key="i" class="feed-row">
				<span class="feed-icon" :class="`tone-${tone(entry.action)}`" aria-hidden="true">
					{{ glyph(entry.action) }}
				</span>
				<div class="feed-body">
					<p class="feed-text">
						<span class="feed-actor">{{ entry.actor || "System" }}</span>
						{{ " " }}{{ describeAuditEntry(entry) }}
					</p>
					<span class="feed-time">{{ formatRelativeTime(entry.timestamp) }}</span>
				</div>
			</li>
		</ul>

		<!-- Load more -->
		<div v-if="hasMore" class="load-more-wrap">
			<button class="load-more-btn" :disabled="loading" @click="$emit('load-more')">
				{{ loading ? "Loading..." : "Load more" }}
			</button>
		</div>
	</div>
</template>

<script setup>
import { ref, computed } from "vue";
import { describeAuditEntry } from "./memberHelpers";
import { formatRelativeTime } from "@/composables/useFormatters";

const props = defineProps({
	entries: { type: Array, default: () => [] },
	loading: { type: Boolean, default: false },
	hasMore: { type: Boolean, default: false },
});

defineEmits(["load-more"]);

// The nine member-management actions (AR/Plan 1). Drives the Event filter.
const ACTIONS = [
	"User Invited",
	"Invite Revoked",
	"Invite Resent",
	"User Activated",
	"User Role Changed",
	"User Credit Limit Changed",
	"User Suspended",
	"User Reactivated",
	"User Removed",
];

const eventFilter = ref("");

const filtered = computed(() => {
	if (!eventFilter.value) return props.entries;
	return props.entries.filter((e) => e.action === eventFilter.value);
});

// Glyph + colour tone per action. Tones map to Quiet-Ledger status tokens:
// accent (neutral/positive), warning (suspend), danger (remove/revoke),
// gold (money). Joins/reactivations read as positive (accent).
const GLYPHS = {
	"User Invited": "✉",
	"Invite Revoked": "✕",
	"Invite Resent": "↻",
	"User Activated": "●",
	"User Role Changed": "↑",
	"User Credit Limit Changed": "◈",
	"User Suspended": "⏸",
	"User Reactivated": "●",
	"User Removed": "✕",
};

const TONES = {
	"User Invited": "accent",
	"Invite Revoked": "danger",
	"Invite Resent": "accent",
	"User Activated": "accent",
	"User Role Changed": "accent",
	"User Credit Limit Changed": "gold",
	"User Suspended": "warning",
	"User Reactivated": "accent",
	"User Removed": "danger",
};

function glyph(action) {
	return GLYPHS[action] || "•";
}

function tone(action) {
	return TONES[action] || "muted";
}
</script>

<style scoped>
.activity-tab {
	margin-top: 1.25rem;
}

/* Header */
.activity-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 0.75rem;
	margin-bottom: 1rem;
	flex-wrap: wrap;
}

.activity-count {
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text-secondary);
}

.filter {
	display: inline-flex;
	align-items: center;
	gap: 0.5rem;
}

.filter-label {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.filter-select {
	font-size: 0.8125rem;
	color: var(--ql-text);
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	padding: 0.375rem 0.5rem;
	cursor: pointer;
}

.filter-select:focus {
	outline: none;
	border-color: var(--ql-accent);
}

/* Loading state */
.loading-state {
	display: flex;
	align-items: center;
	justify-content: center;
	gap: 0.75rem;
	padding: 2.5rem 1rem;
	color: var(--ql-text-muted);
	font-size: 0.875rem;
}

.spinner {
	width: 1.25rem;
	height: 1.25rem;
	animation: spin 1s linear infinite;
}

@keyframes spin {
	from {
		transform: rotate(0deg);
	}
	to {
		transform: rotate(360deg);
	}
}

/* Feed */
.feed {
	list-style: none;
	margin: 0;
	padding: 0;
	display: flex;
	flex-direction: column;
}

.feed-row {
	display: flex;
	align-items: flex-start;
	gap: 0.75rem;
	padding: 0.75rem 0;
	border-bottom: 1px solid var(--ql-border);
}

.feed-row:last-child {
	border-bottom: none;
}

.feed-icon {
	flex-shrink: 0;
	width: 1.75rem;
	height: 1.75rem;
	display: inline-flex;
	align-items: center;
	justify-content: center;
	border-radius: 9999px;
	font-size: 0.85rem;
	line-height: 1;
}

.tone-accent {
	color: var(--ql-accent);
	background: var(--ql-accent-soft);
}

.tone-gold {
	color: var(--ql-gold);
	background: var(--ql-gold-soft);
}

.tone-warning {
	color: var(--ql-warning);
	background: rgba(184, 121, 26, 0.12);
}

.tone-danger {
	color: var(--ql-danger);
	background: rgba(180, 69, 58, 0.12);
}

.tone-muted {
	color: var(--ql-text-muted);
	background: var(--ql-accent-soft);
}

.feed-body {
	display: flex;
	flex-direction: column;
	gap: 0.125rem;
	min-width: 0;
	flex: 1;
}

.feed-text {
	margin: 0;
	font-size: 0.875rem;
	color: var(--ql-text-secondary);
	line-height: 1.4;
	word-break: break-word;
	overflow-wrap: anywhere;
}

.feed-actor {
	font-weight: 600;
	color: var(--ql-text);
}

.feed-time {
	font-size: 0.72rem;
	color: var(--ql-text-muted);
}

/* Empty state */
.empty-state {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 0.5rem;
	padding: 2rem 1rem;
	background: var(--ql-bg);
	border: 1px dashed var(--ql-border);
	border-radius: 0.5rem;
	text-align: center;
}

.empty-icon {
	width: 2.5rem;
	height: 2.5rem;
	color: var(--ql-text-muted);
}

.empty-state p {
	margin: 0;
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
}

/* Load more */
.load-more-wrap {
	display: flex;
	justify-content: center;
	margin-top: 1rem;
}

.load-more-btn {
	font-size: 0.8125rem;
	color: var(--ql-accent);
	background: transparent;
	border: 1px solid var(--ql-accent);
	border-radius: 0.375rem;
	padding: 0.5rem 1.25rem;
	cursor: pointer;
	transition: background 0.15s ease;
}

.load-more-btn:hover:not(:disabled) {
	background: var(--ql-accent-soft);
}

.load-more-btn:disabled {
	opacity: 0.5;
	cursor: not-allowed;
}
</style>
