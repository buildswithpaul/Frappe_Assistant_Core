<template>
	<div class="my-usage">
		<MyCreditsBand />

		<div v-if="loading" class="analytics-state">
			<div class="loading-spinner"></div>
			<p>{{ __("Loading usage data...") }}</p>
		</div>

		<div v-else-if="error" class="analytics-state">
			<p>{{ error }}</p>
			<button class="retry-btn" @click="loadData(range)">{{ __("Retry") }}</button>
		</div>

		<template v-else>
			<SummaryCards :summary="summary" mode="user" :days="range" />

			<div class="section">
				<h3 class="section-title">{{ __("Daily Usage Trend") }}</h3>
				<DailyTrendChart :daily="daily" :by-source="bySource" />
			</div>

			<div class="breakdown-grid">
				<div class="section">
					<h3 class="section-title">{{ __("Usage by Source") }}</h3>
					<SourceBreakdown :sources="bySource" />
				</div>
				<div v-if="byModel.length" class="section">
					<h3 class="section-title">{{ __("Usage by Model") }}</h3>
					<ModelBreakdown :models="byModel" :total-credits="summary.credits_consumed" />
				</div>
			</div>
		</template>
	</div>
</template>

<script setup>
import { onMounted, watch } from "vue";
import SummaryCards from "@/components/analytics/SummaryCards.vue";
import DailyTrendChart from "@/components/analytics/DailyTrendChart.vue";
import SourceBreakdown from "@/components/analytics/SourceBreakdown.vue";
import ModelBreakdown from "@/components/analytics/ModelBreakdown.vue";
import MyCreditsBand from "./MyCreditsBand.vue";
import { useAnalyticsData } from "@/composables/useAnalyticsData";
import { useUserStore } from "@/stores/userStore";
import { __ } from "@/utils/i18n";

const props = defineProps({
	range: { type: Number, default: 30 },
});

const userStore = useUserStore();

const { loading, error, selectedRange, summary, daily, byModel, bySource, loadData } = useAnalyticsData({
	scope: "me",
});

watch(
	() => props.range,
	(days) => {
		selectedRange.value = days;
		loadData(days);
	},
	{ immediate: true },
);

// Boot may have seeded both, but they can be stale; always refresh.
onMounted(() => {
	userStore.loadQuota();
	userStore.loadMyCreditStatus();
});
</script>

<style scoped>
.section {
	margin-bottom: 1.5rem;
}

.section-title {
	font-size: 0.9rem;
	font-weight: 600;
	color: var(--ql-text);
	margin-bottom: 0.75rem;
}

.breakdown-grid {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(min(320px, 100%), 1fr));
	gap: 1.5rem;
}

.breakdown-grid > .section {
	min-width: 0;
}

.analytics-state {
	display: flex;
	flex-direction: column;
	align-items: center;
	padding: 4rem 2rem;
	text-align: center;
	color: var(--ql-text-muted);
	font-size: 0.875rem;
}

.loading-spinner {
	width: 32px;
	height: 32px;
	border: 3px solid var(--ql-border);
	border-top-color: var(--ql-accent);
	border-radius: 50%;
	animation: spin 0.8s linear infinite;
	margin-bottom: 1rem;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

.retry-btn {
	margin-top: 1rem;
	padding: 0.5rem 1rem;
	font-size: 0.875rem;
	color: var(--ql-accent);
	background: transparent;
	border: 1px solid var(--ql-accent);
	border-radius: 0.375rem;
	cursor: pointer;
}
</style>
