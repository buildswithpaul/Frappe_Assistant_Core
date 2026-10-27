<template>
	<div class="summary-grid">
		<div class="summary-card">
			<div class="card-label">{{ __("Credits in the last {0} days", [days]) }}</div>
			<div class="card-value">{{ formatNumber(creditsUsed) }}</div>
			<div class="card-foot">
				<span class="card-sub">{{ __("credits consumed") }}</span>
				<TrendBadge v-if="creditsTrend" :trend="creditsTrend" tone="cost" />
			</div>
		</div>

		<div class="summary-card">
			<div class="card-label" :title="__('Every agent run: one per chat message, one per approval round, and one per background call (classifier, memory, suggestions, workflows). A run can include several model calls.')">{{ __("Agent runs") }}</div>
			<div class="card-value">{{ formatNumber(requestCount) }}</div>
			<div class="card-foot">
				<span class="card-sub">{{ __("chat, approvals and background calls") }}</span>
				<TrendBadge v-if="requestsTrend" :trend="requestsTrend" />
			</div>
		</div>

		<div class="summary-card" v-if="mode === 'admin'">
			<div class="card-label">Active Users</div>
			<div class="card-value">{{ summary.active_users }}</div>
			<div class="card-sub">in this period</div>
		</div>

				<div class="summary-card" v-if="mode === 'admin'">
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
import { __ } from "@/utils/i18n";

const props = defineProps({
	summary: { type: Object, required: true },
	mode: { type: String, default: "admin" }, // 'admin' or 'user'
	days: { type: Number, default: 30 },
	conversationCount: { type: Number, default: 0 },
	// { recent, prior, percent, direction } — see useAnalyticsData.js#trendSplit
	creditsTrend: { type: Object, default: null },
	requestsTrend: { type: Object, default: null },
});

const creditsUsed = computed(() => {
	return Math.round(props.summary.credits_consumed || 0);
});

const requestCount = computed(() => {
	return props.summary.request_count || 0;
});

// Conversations in both modes — `request_count` counts every agent run the
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
