<template>
	<div>
		<div class="usage-chart-header">
			<h3 class="section-title">Prepaid Credit Consumption (Last {{ days }} Days)</h3>
			<select v-model.number="days" class="days-select" @change="loadBreakdown">
				<option :value="7">7 days</option>
				<option :value="30">30 days</option>
				<option :value="90">90 days</option>
			</select>
		</div>
		<div class="chart-card" v-if="hasData">
			<v-chart :option="chartOption" :autoresize="true" class="usage-chart" />
			<p class="chart-note">
				Credits drawn from your purchased balance only. Usage covered by your
				monthly quota is not shown here.
			</p>
		</div>
		<p v-else-if="loading" class="empty-text">Loading…</p>
		<p v-else class="empty-text">
			No prepaid credits used yet — your monthly quota is covering all usage.
		</p>
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
import { vizColor, vizSequence } from "@/composables/dataVizPalette";

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, LegendComponent]);

const { colors } = useChartTheme();

// Known sources in the order they should stack, and the stable index each one
// takes into the shared teal-anchored sequence so a source keeps a consistent,
// on-brand hue across analytics + billing.
//
// This list orders and colours the chart; it does NOT decide what appears in
// it. The chart used to draw only the sources named here and drop every other
// row on the floor — Suggestions, Web Search and Voice Transcription were all
// in the rollup and none of them reached a bar, so the chart under-reported
// without ever looking wrong. AR's source enum grows over time; the chart now
// draws whatever the data holds and this list only says how it should look.
const SOURCE_ORDER = [
	"Chat",
	"Memory Extraction",
	"Workflow",
	"Embedding",
	"Classifier",
	"Voice Transcription",
	"Web Search",
	"Suggestions",
];

// Known sources first in canonical order, then anything new, alphabetically.
function orderedSources(rows) {
	const rank = (s) => {
		const i = SOURCE_ORDER.indexOf(s);
		return i === -1 ? SOURCE_ORDER.length : i;
	};
	return [...new Set(rows.map((r) => r.source))].sort(
		(a, b) => rank(a) - rank(b) || a.localeCompare(b),
	);
}

// Known sources keep their canonical hue. An unknown source takes the first
// hue this particular chart isn't already using, so a newly added AR source
// is legible on sight rather than arriving as a second teal beside Chat.
function sourceColors(sources, isDark) {
	const palette = vizSequence(isDark).length;
	const taken = new Set();
	const index = new Map();

	for (const name of sources) {
		const i = SOURCE_ORDER.indexOf(name);
		if (i !== -1) {
			index.set(name, i);
			taken.add(i % palette);
		}
	}

	let probe = 0;
	for (const name of sources) {
		if (index.has(name)) continue;
		while (probe < palette && taken.has(probe % palette)) probe++;
		index.set(name, probe % palette);
		taken.add(probe % palette);
		probe++;
	}

	return new Map([...index].map(([name, i]) => [name, vizColor(i, isDark)]));
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

	const sources = orderedSources(series.value);
	const palette = sourceColors(sources, colors.value.isDark);

	const datasets = sources.map((source) => {
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
				color: palette.get(source),
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

.chart-note {
	margin: 0.75rem 0 0;
	font-size: 0.75rem;
	line-height: 1.4;
	color: var(--ql-text-muted);
}
</style>
