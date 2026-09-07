<template>
	<div>
		<div class="usage-chart-header">
			<h3 class="section-title">Credit Consumption (Last {{ days }} Days)</h3>
			<select v-model.number="days" class="days-select" @change="loadBreakdown">
				<option :value="7">7 days</option>
				<option :value="30">30 days</option>
				<option :value="90">90 days</option>
			</select>
		</div>
		<div class="chart-card" v-if="hasData">
			<v-chart :option="chartOption" :autoresize="true" class="usage-chart" />
		</div>
		<p v-else-if="loading" class="empty-text">Loading…</p>
		<p v-else class="empty-text">No consumption yet.</p>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import VChart from "vue-echarts";
import { use } from "echarts/core";
import { BarChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";
import { formatTokens } from "@/composables/useFormatters";
import { useChartTheme } from "@/composables/useChartTheme";
import { vizColor } from "@/composables/dataVizPalette";

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, LegendComponent]);

const { colors } = useChartTheme();

// Source taxonomy is fixed by AR Token Usage.source — the chart shows one
// stacked series per source so admins can see what is driving consumption.
const SOURCES = ["Chat", "Memory Extraction", "Workflow", "Embedding", "Classifier"];

// Stable index into the shared teal-anchored sequence so each source keeps a
// consistent, on-brand hue across analytics + billing. Unknown sources fall
// past the known set.
const SOURCE_ORDER = ["Chat", "Memory Extraction", "Workflow", "Embedding", "Classifier"];
function sourceColor(name, isDark) {
	const i = SOURCE_ORDER.indexOf(name);
	return vizColor(i === -1 ? SOURCE_ORDER.length : i, isDark);
}

const days = ref(30);
const loading = ref(false);
const series = ref([]);

async function loadBreakdown() {
	loading.value = true;
	try {
		const result = await api.billing.getConsumptionBreakdown(days.value);
		if (result?.error) {
			logger.warn("Failed to load consumption breakdown:", result.error);
			series.value = [];
			return;
		}
		series.value = result?.series || [];
	} catch (e) {
		logger.warn("Failed to load consumption breakdown:", e);
		series.value = [];
	} finally {
		loading.value = false;
	}
}

const hasData = computed(() => series.value.length > 0);

const chartOption = computed(() => {
	if (!hasData.value) return {};

	// Pivot rows [{date, source, credits}] into a date-axis with one series
	// per source. Missing source/date cells default to 0.
	const dateSet = new Set();
	for (const row of series.value) {
		dateSet.add(row.date);
	}
	const dates = [...dateSet].sort();
	const dateLabels = dates.map((d) => {
		const dt = new Date(d);
		return `${dt.getMonth() + 1}/${dt.getDate()}`;
	});

	const datasets = SOURCES.map((source) => {
		const values = dates.map((d) => {
			const m = series.value.find((r) => r.date === d && r.source === source);
			return m ? Number(m.credits) : 0;
		});
		return {
			name: source,
			type: "bar",
			stack: "credits",
			data: values,
			itemStyle: {
				color: sourceColor(source, colors.value.isDark),
			},
			barMaxWidth: 24,
		};
	}).filter((d) => d.data.some((v) => v > 0));

	return {
		tooltip: {
			trigger: "axis",
			axisPointer: { type: "shadow" },
			formatter: (params) => {
				const date = params[0]?.name;
				let total = 0;
				const lines = params
					.filter((p) => p.value > 0)
					.map((p) => {
						total += Number(p.value);
						return `${p.marker} ${p.seriesName}: ${formatTokens(p.value)}`;
					});
				return [
					`<strong>${date}</strong>`,
					...lines,
					`Total: ${formatTokens(total)}`,
				].join("<br/>");
			},
		},
		legend: {
			data: datasets.map((d) => d.name),
			textStyle: { color: colors.value.muted, fontSize: 11 },
			top: 0,
		},
		grid: {
			left: "3%",
			right: "4%",
			bottom: "3%",
			top: "12%",
			containLabel: true,
		},
		xAxis: {
			type: "category",
			data: dateLabels,
			axisLabel: { fontSize: 11, color: colors.value.muted },
			axisLine: { lineStyle: { color: colors.value.border } },
		},
		yAxis: {
			type: "value",
			axisLabel: {
				fontSize: 11,
				color: colors.value.muted,
				formatter: (val) => formatTokens(val),
			},
			splitLine: { lineStyle: { color: colors.value.border, type: "dashed" } },
		},
		series: datasets,
	};
});

onMounted(loadBreakdown);
</script>

<style scoped>
.usage-chart-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	margin-bottom: 0.5rem;
}

.section-title {
	font-size: 1rem;
	font-weight: 600;
	color: var(--ql-text);
}

.days-select {
	padding: 0.25rem 0.5rem;
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	background: var(--ql-bg);
	color: var(--ql-text);
	font-size: 0.8125rem;
}

.chart-card {
	padding: 1rem;
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
}

.usage-chart {
	height: 280px;
	width: 100%;
}

.empty-text {
	font-size: 0.875rem;
	color: var(--ql-text-muted);
}
</style>
