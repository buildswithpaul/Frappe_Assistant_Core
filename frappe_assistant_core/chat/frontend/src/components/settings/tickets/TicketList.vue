<template>
	<div class="ticket-list">
		<div class="list-toolbar">
			<select class="status-filter" :value="filter" @change="onFilter">
				<option value="">All</option>
				<option value="Open">Open</option>
				<option value="Replied">Replied</option>
				<option value="Resolved">Resolved</option>
				<option value="Closed">Closed</option>
			</select>
		</div>

		<div v-if="loading" class="list-loading">
			<div class="skeleton-row"></div>
			<div class="skeleton-row"></div>
			<div class="skeleton-row"></div>
		</div>

		<div v-else-if="tickets.length === 0" class="list-empty">
			<p>No tickets yet. Raise one from the Help &amp; Feedback button.</p>
		</div>

		<ul v-else class="rows">
			<li
				v-for="t in tickets"
				:key="t.name"
				class="row"
				@click="$emit('select', t.name)"
			>
				<div class="row-main">
					<span class="row-subject">{{ t.subject }}</span>
					<TicketStatusPill :status="t.status" />
				</div>
				<span class="row-date">{{ formatDate(t.modified) }}</span>
			</li>
		</ul>
	</div>
</template>

<script setup>
import { ref } from "vue";
import TicketStatusPill from "./TicketStatusPill.vue";

defineProps({
	tickets: { type: Array, default: () => [] },
	loading: { type: Boolean, default: false },
});

const emit = defineEmits(["select", "filter"]);

const filter = ref("");

function onFilter(e) {
	filter.value = e.target.value;
	emit("filter", filter.value);
}

function formatDate(value) {
	if (!value) return "";
	return new Date(value).toLocaleDateString();
}
</script>

<style scoped>
.ticket-list {
	display: flex;
	flex-direction: column;
	gap: 0.75rem;
}

.list-toolbar {
	display: flex;
	justify-content: flex-end;
}

.status-filter {
	font-size: 0.85rem;
	padding: 0.35rem 0.6rem;
	border: 1px solid var(--ql-border, #e2e8f0);
	border-radius: 6px;
	background: var(--ql-surface, #fff);
	color: var(--ql-text, #1e293b);
	cursor: pointer;
}

.list-loading {
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
}

.skeleton-row {
	height: 48px;
	background: var(--ql-border, #e2e8f0);
	border-radius: 8px;
	animation: skeleton-pulse 1.5s ease-in-out infinite;
}

@keyframes skeleton-pulse {
	0%,
	100% {
		opacity: 0.4;
	}
	50% {
		opacity: 0.8;
	}
}

.list-empty {
	text-align: center;
	padding: 2rem 1rem;
	color: var(--ql-text-muted, #64748b);
	font-size: 0.9rem;
}

.rows {
	list-style: none;
	margin: 0;
	padding: 0;
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
}

.row {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 1rem;
	padding: 0.75rem 0.9rem;
	border: 1px solid var(--ql-border, #e2e8f0);
	border-radius: 8px;
	cursor: pointer;
	transition: background 0.15s ease, border-color 0.15s ease;
}

.row:hover {
	background: var(--ql-subtle, #f1f5f9);
	border-color: var(--ql-accent, #cbd5e1);
}

.row-main {
	display: flex;
	align-items: center;
	gap: 0.6rem;
	min-width: 0;
}

.row-subject {
	font-size: 0.9rem;
	font-weight: 500;
	color: var(--ql-text, #1e293b);
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.row-date {
	font-size: 0.78rem;
	color: var(--ql-text-muted, #94a3b8);
	white-space: nowrap;
}
</style>
