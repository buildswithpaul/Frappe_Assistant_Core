<template>
	<ExpandableArtifact
		:capture="captureChart"
		:can-capture="chartReady"
		:to-png="exportPng"
		:disabled="isStreaming"
		title="chart"
	>
		<div class="chart-container">
			<div v-if="error" class="chart-error">
				<svg class="error-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
					/>
				</svg>
				<span>{{ errorMessage }}</span>
			</div>
			<v-chart
				v-else
				ref="chartRef"
				:option="chartOption"
				:autoresize="true"
				class="chart"
			/>
		</div>
	</ExpandableArtifact>
</template>

<script setup>
import { computed, ref, onMounted, nextTick } from "vue";
import { logger } from "@/utils/logger";
import VChart from "vue-echarts";
import { use, init as echartsInit } from "echarts/core";
import ExpandableArtifact from "./artifact/ExpandableArtifact.vue";
import { BarChart, LineChart, PieChart, ScatterChart } from "echarts/charts";
import {
	GridComponent,
	TooltipComponent,
	LegendComponent,
	TitleComponent,
	DatasetComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

// Register ECharts components (tree-shaking friendly)
use([
	CanvasRenderer,
	BarChart,
	LineChart,
	PieChart,
	ScatterChart,
	GridComponent,
	TooltipComponent,
	LegendComponent,
	TitleComponent,
	DatasetComponent,
]);

const props = defineProps({
	config: {
		type: Object,
		required: true,
	},
	isStreaming: {
		type: Boolean,
		default: false,
	},
});

const error = ref(false);
const errorMessage = ref("Failed to render chart");
const chartRef = ref(null);
const chartMounted = ref(false);

onMounted(async () => {
	await nextTick();
	chartMounted.value = true;
});

// Valid chart types
const VALID_CHART_TYPES = ["bar", "line", "pie", "scatter"];

// Validate chart configuration
function validateConfig(config) {
	if (!config || typeof config !== "object") {
		return { valid: false, message: "Invalid chart configuration" };
	}

	if (!VALID_CHART_TYPES.includes(config.type)) {
		return { valid: false, message: `Unsupported chart type: ${config.type}` };
	}

	if (!config.data) {
		return { valid: false, message: "Missing chart data" };
	}

	if (!config.data.categories || !Array.isArray(config.data.categories)) {
		return { valid: false, message: "Missing or invalid categories" };
	}

	if (!config.data.series || !Array.isArray(config.data.series)) {
		return { valid: false, message: "Missing or invalid series data" };
	}

	return { valid: true };
}

// Transform LLM JSON to ECharts option format
const chartOption = computed(() => {
	try {
		const validation = validateConfig(props.config);
		if (!validation.valid) {
			error.value = true;
			errorMessage.value = validation.message;
			return {};
		}

		error.value = false;
		const { type, title, data } = props.config;

		// Base configuration
		const option = {
			title: title
				? {
						text: title,
						left: "center",
						textStyle: {
							fontSize: 14,
							fontWeight: 500,
						},
				  }
				: undefined,
			tooltip: {
				trigger: type === "pie" ? "item" : "axis",
				backgroundColor: "rgba(255, 255, 255, 0.95)",
				borderColor: "#e5e7eb",
				borderWidth: 1,
				textStyle: {
					color: "#374151",
				},
			},
			legend: {
				bottom: 0,
				type: "scroll",
				textStyle: {
					fontSize: 12,
				},
			},
			grid:
				type !== "pie"
					? {
							left: "3%",
							right: "4%",
							bottom: "15%",
							top: title ? "15%" : "8%",
							containLabel: true,
					  }
					: undefined,
		};

		// Add axes for non-pie charts
		if (type !== "pie") {
			option.xAxis = {
				type: "category",
				data: data.categories,
				axisLabel: {
					rotate: data.categories.length > 6 ? 45 : 0,
					fontSize: 11,
				},
			};
			option.yAxis = {
				type: "value",
				axisLabel: {
					fontSize: 11,
				},
			};
		}

		// Build series
		option.series = data.series.map((s, index) => {
			const seriesConfig = {
				name: s.name || `Series ${index + 1}`,
				type: type,
			};

			if (type === "pie") {
				// Pie chart data format
				seriesConfig.radius = ["40%", "70%"];
				seriesConfig.center = ["50%", "50%"];
				seriesConfig.data = data.categories.map((cat, i) => ({
					name: cat,
					value: s.values[i],
				}));
				seriesConfig.emphasis = {
					itemStyle: {
						shadowBlur: 10,
						shadowOffsetX: 0,
						shadowColor: "rgba(0, 0, 0, 0.3)",
					},
				};
				seriesConfig.label = {
					show: true,
					formatter: "{b}: {d}%",
				};
			} else {
				// Bar, line, scatter data format
				seriesConfig.data = s.values;

				if (type === "line") {
					seriesConfig.smooth = true;
					seriesConfig.symbol = "circle";
					seriesConfig.symbolSize = 6;
				}

				if (type === "bar") {
					seriesConfig.barMaxWidth = 40;
				}
			}

			return seriesConfig;
		});

		return option;
	} catch (e) {
		logger.error("Chart rendering error:", e);
		error.value = true;
		errorMessage.value = "Error processing chart data";
		return {};
	}
});

// Cheap predicate for ExpandableArtifact visibility — is the chart rendered
// and healthy? Allocation-free (does NOT init an ECharts instance). The
// chartOption computed sets error.value for invalid configs, so reading it
// here also ensures the option has been evaluated.
function chartReady() {
	// touch chartOption so error.value reflects the latest config
	const opt = chartOption.value;
	return chartMounted.value && !error.value && !!opt && !!chartRef.value?.chart;
}

// Export adapter: the inline chart's own getDataURL at 2x, white background.
function exportPng() {
	const inst = chartRef.value?.chart;
	if (!inst) return Promise.reject(new Error("No chart to export"));
	return Promise.resolve(
		inst.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#fff" })
	);
}

// Capture adapter (modal-only): build a FRESH ECharts instance from the same
// option into a detached div sized for the modal. cleanup() disposes it to
// avoid leaking an instance + canvas per expand.
function captureChart() {
	if (!chartReady()) return null;
	const node = document.createElement("div");
	node.style.width = "1200px";
	node.style.height = "800px";
	const inst = echartsInit(node);
	inst.setOption(chartOption.value);
	return { node, cleanup: () => inst.dispose() };
}
</script>

<style scoped>
.chart-container {
	margin: 1rem 0;
	padding: 1rem;
	background-color: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
}

.chart {
	height: 320px;
	width: 100%;
}

.chart-error {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	gap: 0.75rem;
	padding: 2rem;
	color: var(--ql-text-muted);
	font-size: 0.875rem;
	text-align: center;
}

.error-icon {
	width: 2rem;
	height: 2rem;
	color: #f59e0b;
}

/* Responsive chart height */
@media (max-width: 640px) {
	.chart {
		height: 280px;
	}
}
</style>
