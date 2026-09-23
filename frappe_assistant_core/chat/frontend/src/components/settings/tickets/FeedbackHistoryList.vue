<template>
	<div class="feedback-history">
		<div v-if="loading" class="list-loading">
			<div class="skeleton-row"></div>
			<div class="skeleton-row"></div>
			<div class="skeleton-row"></div>
		</div>

		<div v-else-if="error" class="list-error">
			<p>{{ error }}</p>
			<button type="button" class="retry-btn" @click="$emit('retry')">Try Again</button>
		</div>

		<div v-else-if="items.length === 0" class="list-empty">
			<p>You haven't sent us any feedback yet.</p>
		</div>

		<ul v-else class="rows">
			<li v-for="item in items" :key="item.name" class="row">
				<div class="row-top">
					<span class="fb-status">{{ item.status }}</span>
					<span v-if="item.rating" class="fb-rating">
						<span v-for="n in item.rating" :key="n">★</span>
					</span>
					<span class="row-time">{{ formatRelativeTime(item.submitted_at) }}</span>
				</div>
				<p v-if="item.comment" class="row-comment">{{ item.comment }}</p>
				<div class="row-bottom">
					<span v-if="item.category" class="fb-category">{{ item.category }}</span>
					<button
						v-if="item.escalated_ticket"
						type="button"
						class="view-ticket-btn"
						@click="$emit('open-ticket', item.escalated_ticket)"
					>
						View ticket →
					</button>
				</div>
			</li>
		</ul>
	</div>
</template>

<script setup>
import { formatRelativeTime } from "@/composables/useFormatters";

defineProps({
	items: { type: Array, default: () => [] },
	loading: { type: Boolean, default: false },
	error: { type: String, default: null },
});

defineEmits(["open-ticket", "retry"]);
</script>

<style scoped>
.feedback-history {
	display: flex;
	flex-direction: column;
	gap: 0.75rem;
}

.list-loading {
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
}

.skeleton-row {
	height: 64px;
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

.list-error {
	text-align: center;
	padding: 1.5rem;
	color: var(--ql-text-muted, #64748b);
}

.retry-btn {
	margin-top: 0.5rem;
	padding: 0.25rem 0.75rem;
	font-size: 0.8rem;
	border: 1px solid var(--ql-border, #e2e8f0);
	border-radius: 6px;
	background: transparent;
	cursor: pointer;
	color: var(--ql-text, #1e293b);
}

.retry-btn:hover {
	background: var(--ql-subtle, #f1f5f9);
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
	flex-direction: column;
	gap: 0.4rem;
	padding: 0.75rem 0.9rem;
	border: 1px solid var(--ql-border, #e2e8f0);
	border-radius: 8px;
}

.row-top {
	display: flex;
	align-items: center;
	gap: 0.6rem;
}

.fb-status {
	font-size: 0.75rem;
	padding: 0.1rem 0.5rem;
	border-radius: 999px;
	font-weight: 600;
	background: var(--ql-subtle, #f1f5f9);
	color: var(--ql-text-secondary, #475467);
}

.fb-rating {
	color: var(--ql-gold, #d4a72c);
	font-size: 0.85rem;
	line-height: 1;
}

.row-time {
	margin-left: auto;
	font-size: 0.78rem;
	color: var(--ql-text-muted, #94a3b8);
	white-space: nowrap;
}

.row-comment {
	margin: 0;
	font-size: 0.88rem;
	color: var(--ql-text, #1e293b);
}

.row-bottom {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 0.6rem;
}

.fb-category {
	font-size: 0.78rem;
	color: var(--ql-text-muted, #94a3b8);
}

.view-ticket-btn {
	margin-left: auto;
	font-size: 0.82rem;
	font-weight: 500;
	color: var(--ql-accent, #2563eb);
	background: none;
	border: none;
	cursor: pointer;
	padding: 0;
}

.view-ticket-btn:hover {
	text-decoration: underline;
}
</style>
