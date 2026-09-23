<template>
	<div class="chart-card" v-if="models.length">
		<v-chart :option="chartOption" :autoresize="true" class="model-chart" />
	</div>
	<p v-else class="empty-text">No model data available</p>
</template>

<script setup>
import { computed } from "vue";
import VChart from "vue-echarts";
import { use } from "echarts/core";
import { BarChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { useChartTheme } from "@/composables/useChartTheme";
import { vizColor } from "@/composables/dataVizPalette";

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent]);

const { colors } = useChartTheme();

const props = defineProps({
	models: { type: Array, default: () => [] },
	totalCredits: { type: Number, default: 0 },
});

function shortenModelId(id) {
	if (!id) return "unknown";
	return id.replace(/-\d{8}$/, "");
}

function getModelPercent(model) {
	const total = props.totalCredits;
	const value = model.credits_consumed || 0;
	if (!total || !value) return 0;
	return Math.round((value / total) * 100);
}

const chartOption = computed(() => {
	if (!props.models.length) return {};

	const names = props.models.map((m) => shortenModelId(m.model_id));
	const percentages = props.models.map((m) => getModelPercent(m));

	return {
		tooltip: {
			trigger: "axis",
			axisPointer: { type: "shadow" },
			formatter: (params) => {
				const p = params[0];
				const model = props.models[p.dataIndex];
				return `<strong>${shortenModelId(model.model_id)}</strong><br/>${
					p.value
				}% of usage`;
			},
		},
		grid: {
			left: "3%",
			right: "8%",
			bottom: "3%",
			top: "3%",
			containLabel: true,
		},
		xAxis: {
			type: "value",
			max: 100,
			axisLabel: {
				fontSize: 11,
				color: colors.value.muted,
				formatter: (val) => `${val}%`,
			},
			splitLine: { lineStyle: { color: colors.value.border, type: "dashed" } },
		},
		yAxis: {
			type: "category",
			data: names,
			axisLabel: { fontSize: 12, color: colors.value.textSecondary },
			axisLine: { lineStyle: { color: colors.value.border } },
		},
		series: [
			{
				type: "bar",
				data: percentages.map((v, i) => ({
					value: v,
					itemStyle: {
						color: vizColor(i, colors.value.isDark),
						borderRadius: [0, 3, 3, 0],
					},
				})),
				barMaxWidth: 24,
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

.model-chart {
	height: 260px;
	width: 100%;
}

.empty-text {
	font-size: 0.875rem;
	color: var(--ql-text-muted);
}
</style>
