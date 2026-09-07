<template>
	<div class="chart-card" v-if="daily.length">
		<v-chart :option="chartOption" :autoresize="true" class="trend-chart" />
	</div>
	<p v-else class="empty-text">No daily usage data available</p>
</template>

<script setup>
import { computed } from "vue";
import VChart from "vue-echarts";
import { use } from "echarts/core";
import { BarChart } from "echarts/charts";
import { GridComponent, TooltipComponent, MarkPointComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { useChartTheme } from "@/composables/useChartTheme";
import { vizPeak, vizFade } from "@/composables/dataVizPalette";

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, MarkPointComponent]);

const { colors } = useChartTheme();

const props = defineProps({
	daily: { type: Array, default: () => [] },
	// bySource is kept in the prop list for forward compat; true per-day
	// stacking would require a daily×source matrix from the backend. Today
	// we just use the totals for the tooltip footer composition hint.
	bySource: { type: Array, default: () => [] },
});

// Compact Y-axis labels: 1200 → "1.2K", 1450000 → "1.45M"
function compactNumber(val) {
	if (val == null) return "";
	const abs = Math.abs(val);
	if (abs >= 1_000_000) return (val / 1_000_000).toFixed(abs >= 10_000_000 ? 0 : 1) + "M";
	if (abs >= 1_000) return (val / 1_000).toFixed(abs >= 10_000 ? 0 : 1) + "K";
	return String(Math.round(val));
}

const chartOption = computed(() => {
	if (!props.daily.length) return {};

	const dates = props.daily.map((item) => {
		const d = new Date(item.date);
		return `${d.getMonth() + 1}/${d.getDate()}`;
	});

	const credits = props.daily.map((d) => Math.round(d.credits_consumed || 0));
	const requests = props.daily.map((d) => d.request_count || 0);

	// Derive a source-composition hint for the tooltip (period-wide ratio,
	// not per-day). Better than nothing until the backend sends daily×source.
	const totalCredits = credits.reduce((a, b) => a + b, 0);
	const sourceShare = props.bySource
		.map((s) => {
			const share = totalCredits
				? Math.round(((s.credits_consumed || 0) / totalCredits) * 100)
				: 0;
			return share >= 1 ? { source: s.source, share } : null;
		})
		.filter(Boolean)
		.slice(0, 3);

	// Peak day — highlighted so the spike tells a story instead of just
	// being the tallest bar.
	const maxCredit = Math.max(...credits);
	const peakIdx = maxCredit > 0 ? credits.indexOf(maxCredit) : -1;

	return {
		tooltip: {
			trigger: "axis",
			formatter: (params) => {
				const idx = params[0]?.dataIndex ?? 0;
				const creditVal = credits[idx] || 0;
				const reqVal = requests[idx] || 0;
				const dateLabel = params[0]?.name || "";
				if (!creditVal) return `<strong>${dateLabel}</strong><br/>No usage`;
				let html = `<strong>${dateLabel}</strong><br/>${creditVal.toLocaleString()} credits`;
				html += ` <span style="color:#8A857C">(${reqVal.toLocaleString()} requests)</span>`;
				if (sourceShare.length) {
					html += '<br/><span style="color:#8A857C;font-size:11px">Mostly ';
					html += sourceShare
						.map((s) => `${s.source.toLowerCase()} ${s.share}%`)
						.join(" · ");
					html += "</span>";
				}
				return html;
			},
		},
		grid: {
			left: "1%",
			right: "4%",
			bottom: "3%",
			top: "3%",
			containLabel: true,
		},
		xAxis: {
			type: "category",
			data: dates,
			axisLabel: { fontSize: 11, color: colors.value.muted },
			axisLine: { lineStyle: { color: colors.value.border } },
		},
		yAxis: {
			type: "value",
			axisLabel: {
				fontSize: 11,
				color: colors.value.muted,
				formatter: compactNumber,
			},
			axisTick: { show: false },
			splitLine: { lineStyle: { color: colors.value.border, type: "dashed" } },
		},
		series: [
			{
				name: "Credits",
				type: "bar",
				data: credits.map((v, i) => ({
					value: v,
					// Peak day gets the full primary color; other days a
					// subdued tint so the eye lands on the spike.
					itemStyle: {
						color: i === peakIdx ? vizPeak(colors.value.isDark) : vizFade(colors.value.isDark),
						borderRadius: [3, 3, 0, 0],
					},
				})),
				barMaxWidth: 20,
				markPoint:
					peakIdx >= 0 && credits.length > 5
						? {
								symbol: "pin",
								symbolSize: 32,
								itemStyle: { color: vizPeak(colors.value.isDark) },
								label: { color: "#fff", fontSize: 10, fontWeight: 600 },
								data: [
									{
										name: "Peak",
										value: compactNumber(maxCredit),
										coord: [peakIdx, maxCredit],
									},
								],
						  }
						: undefined,
			},
		],
	};
});
</script>

<style scoped>
.chart-card {
	padding: 1rem;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
}

.trend-chart {
	height: 280px;
	width: 100%;
}

.empty-text {
	font-size: 0.875rem;
	color: var(--ql-text-muted);
}
</style>
