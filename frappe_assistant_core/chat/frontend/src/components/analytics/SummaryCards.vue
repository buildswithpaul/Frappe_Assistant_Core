<template>
	<div class="summary-grid">
		<div class="summary-card">
			<div class="card-label">
				{{ mode === "user" ? "My Credits Used" : "Credits Used" }}
			</div>
			<div class="card-value credit-display" v-if="quotaTotal > 0">
				{{ formatNumber(creditsUsed) }}
				<span class="credit-total">/ {{ formatNumber(quotaTotal) }}</span>
			</div>
			<div class="card-value" v-else>{{ formatNumber(creditsUsed) }}</div>
			<div class="card-foot">
				<span class="card-sub" v-if="quotaTotal > 0"
					>{{ usagePercent }}% of monthly quota</span
				>
				<span class="card-sub" v-else>credits consumed</span>
				<TrendBadge v-if="creditsTrend" :trend="creditsTrend" tone="cost" />
			</div>
		</div>

		<div class="summary-card">
			<div class="card-label">Remaining</div>
			<div class="card-value" v-if="quotaTotal > 0">{{ formatNumber(remaining) }}</div>
			<div class="card-value" v-else-if="isUnlimited">&infin;</div>
			<div class="card-value" v-else>&mdash;</div>
			<div class="card-sub">credits remaining</div>
		</div>

		<div class="summary-card">
			<div class="card-label">Total Requests</div>
			<div class="card-value">{{ formatNumber(requestCount) }}</div>
			<div class="card-foot">
				<span class="card-sub">API calls</span>
				<TrendBadge v-if="requestsTrend" :trend="requestsTrend" />
			</div>
		</div>

		<div class="summary-card" v-if="mode === 'admin'">
			<div class="card-label">Active Users</div>
			<div class="card-value">{{ summary.active_users }}</div>
			<div class="card-sub">in this period</div>
		</div>

		<div class="summary-card" v-if="mode === 'user'">
			<div class="card-label">My Conversations</div>
			<div class="card-value">{{ formatNumber(conversationCount) }}</div>
			<div class="card-sub">in this period</div>
		</div>

		<div class="summary-card">
			<div class="card-label">Avg per Chat</div>
			<div class="card-value" v-if="avgDenominator > 0">{{ formatNumber(avgPerChat) }}</div>
			<div class="card-value" v-else>&mdash;</div>
			<div class="card-sub">credits per conversation (all sources)</div>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import TrendBadge from "./TrendBadge.vue";

const props = defineProps({
	summary: { type: Object, required: true },
	quota: { type: Object, default: null },
	mode: { type: String, default: "admin" }, // 'admin' or 'user'
	conversationCount: { type: Number, default: 0 },
	// { recent, prior, percent, direction } — see useAnalyticsData.js#trendSplit
	creditsTrend: { type: Object, default: null },
	requestsTrend: { type: Object, default: null },
});

const quotaTotal = computed(() => {
	const total = props.quota?.quota_total || 0;
	return total > 0 ? total : 0;
});

const isUnlimited = computed(() => {
	return props.quota?.quota_total === -1 || props.quota?.unlimited === true;
});

const creditsUsed = computed(() => {
	return Math.round(props.summary.credits_consumed || 0);
});

const remaining = computed(() => {
	return Math.max(0, quotaTotal.value - creditsUsed.value);
});

const requestCount = computed(() => {
	return props.summary.request_count || 0;
});

// Conversations in both modes — `request_count` counts every API call the
// period made (chat, suggestions, classification, web search), so dividing by
// it answered "credits per request" under a label promising per conversation.
// Zero conversations yields a dash rather than a number: after a GDPR erase the
// credits outlive the conversations they were spent on, and there is nothing
// honest to average.
const avgDenominator = computed(() => props.conversationCount);

const avgPerChat = computed(() => {
	if (!avgDenominator.value) return 0;
	return Math.round(creditsUsed.value / avgDenominator.value);
});

const usagePercent = computed(() => {
	if (!quotaTotal.value) return 0;
	return Math.round((creditsUsed.value / quotaTotal.value) * 100);
});

function formatNumber(val) {
	if (!val && val !== 0) return "0";
	return Number(val).toLocaleString();
}
</script>

<style scoped>
.summary-grid {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
	gap: 1rem;
	margin-bottom: 1.5rem;
}

.summary-card {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	padding: 1.25rem;
}

.card-label {
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.05em;
	margin-bottom: 0.5rem;
}

.card-value {
	font-size: 1.75rem;
	font-weight: 700;
	color: var(--ql-text);
	line-height: 1.2;
	font-family: ui-monospace, "SF Mono", SFMono-Regular, Menlo, monospace;
	font-variant-numeric: tabular-nums;
}

.card-value.credit-display {
	font-size: 1.25rem;
}

.credit-total {
	font-size: 0.875rem;
	font-weight: 400;
	color: var(--ql-text-muted);
	font-family: ui-monospace, "SF Mono", SFMono-Regular, Menlo, monospace;
	font-variant-numeric: tabular-nums;
}

.card-sub {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	margin-top: 0.25rem;
}

.card-foot {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 0.5rem;
	margin-top: 0.25rem;
}

.card-foot .card-sub {
	margin-top: 0;
}
</style>
