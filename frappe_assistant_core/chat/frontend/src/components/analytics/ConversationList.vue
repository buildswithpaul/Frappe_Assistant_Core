<template>
	<div class="conversation-list">
		<p class="scope-note">
			Chat credits only — suggestions and other assistant activity are listed under
			Usage by Source.
		</p>

		<div class="conversation-list-card" v-if="conversations.length || loading">
			<table class="conv-table">
				<thead>
					<tr>
						<th class="col-title">Conversation</th>
						<th class="col-user" v-if="isAdmin">User</th>
						<th class="col-num">Credits</th>
						<th class="col-num">Messages</th>
						<th class="col-date">Last Active</th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="conv in conversations"
						:key="conv.conversation_id"
						class="conv-row"
						@click="$emit('select', conv.conversation_id)"
					>
						<td class="col-title">
							<span class="conv-title">{{ conv.title || "Untitled" }}</span>
						</td>
						<td class="col-user" v-if="isAdmin">
							<span class="user-id">{{ shortenUser(conv.user_id) }}</span>
						</td>
						<td class="col-num">
							<div class="credit-cell">
								<div class="credit-bar-bg">
									<div
										class="credit-bar"
										:class="{ 'is-outlier': isOutlier(conv) }"
										:style="{ width: getCreditPercent(conv) + '%' }"
										:title="
											isOutlier(conv)
												? 'Top 10% of conversations by credit spend'
												: ''
										"
									></div>
								</div>
								<span
									class="credit-value"
									:class="{ 'is-outlier': isOutlier(conv) }"
									>{{ formatCredits(conv.total_credits) }}</span
								>
							</div>
						</td>
						<td class="col-num">{{ conv.message_count }}</td>
						<td class="col-date">{{ formatDate(conv.last_message_at) }}</td>
					</tr>
				</tbody>
			</table>

			<div v-if="loading" class="loading-row">
				<div class="loading-spinner-sm"></div>
			</div>

			<button v-else-if="hasMore" class="load-more-btn" @click="$emit('load-more')">
				Load more conversations
			</button>
		</div>
		<p v-else class="empty-text">No conversation data available for this period</p>
	</div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
	conversations: { type: Array, default: () => [] },
	isAdmin: { type: Boolean, default: false },
	loading: { type: Boolean, default: false },
	hasMore: { type: Boolean, default: false },
	totalCredits: { type: Number, default: 0 },
});

defineEmits(["select", "load-more"]);

function formatCredits(val) {
	if (!val) return "0";
	return Math.round(val).toLocaleString();
}

function getCreditPercent(conv) {
	if (!props.totalCredits || !conv.total_credits) return 0;
	return Math.min(100, Math.round((conv.total_credits / props.totalCredits) * 100));
}

// Outlier threshold = 90th percentile of credit spend in the currently
// loaded page. Conversations at or above this bar are visually flagged so
// cost drivers stand out without needing to sort. Falls back to 0 when
// we don't have enough data (fewer than 5 conversations) to avoid
// flagging everything as "outlier".
const outlierThreshold = computed(() => {
	const values = props.conversations
		.map((c) => c.total_credits || 0)
		.filter((v) => v > 0)
		.sort((a, b) => a - b);
	if (values.length < 5) return Infinity;
	const idx = Math.floor(values.length * 0.9);
	return values[idx] || Infinity;
});

function isOutlier(conv) {
	return (conv.total_credits || 0) >= outlierThreshold.value;
}

function shortenUser(userId) {
	if (!userId) return "—";
	const atIdx = userId.indexOf("@");
	if (atIdx > 0) return userId.substring(0, atIdx);
	return userId.length > 20 ? userId.substring(0, 20) + "..." : userId;
}

function formatDate(isoStr) {
	if (!isoStr) return "—";
	const d = new Date(isoStr);
	const now = new Date();
	const diffMs = now - d;
	const diffDays = Math.floor(diffMs / 86400000);

	if (diffDays === 0) {
		return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
	} else if (diffDays === 1) {
		return "Yesterday";
	} else if (diffDays < 7) {
		return `${diffDays}d ago`;
	}
	return d.toLocaleDateString([], { month: "short", day: "numeric" });
}
</script>

<style scoped>
.scope-note {
	margin: -0.35rem 0 0.75rem;
	font-size: 0.8125rem;
	line-height: 1.45;
	color: var(--ql-text-muted);
}

.conversation-list-card {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	overflow: hidden;
}

.conv-table {
	width: 100%;
	border-collapse: collapse;
	font-size: 0.875rem;
}

.conv-table thead {
	background: var(--ql-bg);
}

.conv-table th {
	padding: 0.75rem 1rem;
	font-weight: 600;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.05em;
	text-align: left;
	border-bottom: 1px solid var(--ql-border);
}

.conv-table td {
	padding: 0.75rem 1rem;
	color: var(--ql-text);
	border-bottom: 1px solid var(--ql-border);
}

.conv-row {
	cursor: pointer;
	transition: background 0.15s ease;
}

.conv-row:hover {
	background: var(--ql-subtle);
}

.conv-row:last-child td {
	border-bottom: none;
}

.col-title {
	max-width: 300px;
}

.conv-title {
	font-weight: 500;
	color: var(--ql-text);
	display: block;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.col-user {
	max-width: 160px;
}

.user-id {
	font-size: 0.8125rem;
	color: var(--ql-text-secondary);
}

.col-num {
	text-align: right !important;
	white-space: nowrap;
}

.col-date {
	text-align: right !important;
	white-space: nowrap;
	color: var(--ql-text-muted);
	font-size: 0.8125rem;
}

.credit-cell {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	justify-content: flex-end;
}

.credit-bar-bg {
	width: 60px;
	height: 6px;
	background: var(--ql-bg);
	border-radius: 3px;
	overflow: hidden;
}

.credit-bar {
	height: 100%;
	background: var(--ql-accent);
	border-radius: 3px;
	min-width: 2px;
	transition: width 0.3s ease;
}

.credit-bar.is-outlier {
	background: var(--ql-gold);
}

.credit-value {
	font-weight: 600;
	font-size: 0.8125rem;
	min-width: 3rem;
	text-align: right;
}

.credit-value.is-outlier {
	color: var(--ql-warning);
}

.loading-row {
	display: flex;
	justify-content: center;
	padding: 1rem;
}

.loading-spinner-sm {
	width: 20px;
	height: 20px;
	border: 2px solid var(--ql-border);
	border-top-color: var(--ql-accent);
	border-radius: 50%;
	animation: spin 0.8s linear infinite;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

.load-more-btn {
	display: block;
	width: 100%;
	padding: 0.75rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-accent);
	background: transparent;
	border: none;
	border-top: 1px solid var(--ql-border);
	cursor: pointer;
	transition: background 0.15s ease;
}

.load-more-btn:hover {
	background: var(--ql-subtle);
}

.empty-text {
	font-size: 0.875rem;
	color: var(--ql-text-muted);
}

@media (max-width: 768px) {
	.conv-table {
		font-size: 0.8rem;
	}

	.conv-table th,
	.conv-table td {
		padding: 0.5rem;
	}

	.col-date {
		display: none;
	}

	.credit-bar-bg {
		display: none;
	}
}
</style>
