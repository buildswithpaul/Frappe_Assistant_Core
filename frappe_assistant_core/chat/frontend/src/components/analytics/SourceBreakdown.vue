<template>
	<div class="source-breakdown" v-if="sources.length">
		<div class="source-list">
			<div v-for="source in sortedSources" :key="source.source" class="source-row">
				<div class="source-info">
					<span
						class="source-dot"
						:style="{ background: getColor(source.source) }"
					></span>
					<span class="source-name">{{ source.source }}</span>
				</div>
				<div class="source-bar-wrapper">
					<div
						class="source-bar"
						:style="{
							width: getPercent(source) + '%',
							background: getColor(source.source),
						}"
					></div>
				</div>
				<div class="source-stats">
					<span class="source-credits">{{ formatNumber(getCredits(source)) }}</span>
					<span class="source-percent">({{ getPercent(source) }}%)</span>
				</div>
			</div>
		</div>
	</div>
	<p v-else class="empty-text">No source data available</p>
</template>

<script setup>
import { computed } from "vue";
import { useChartTheme } from "@/composables/useChartTheme";
import { vizColor } from "@/composables/dataVizPalette";

const { colors } = useChartTheme();

// Stable index into the shared teal-anchored sequence so each source keeps a
// consistent, on-brand hue. Unknown sources fall past the known set.
const SOURCE_ORDER = ["Chat", "Memory Extraction", "Workflow", "Embedding", "Classifier"];
function sourceColor(name, isDark) {
	const i = SOURCE_ORDER.indexOf(name);
	return vizColor(i === -1 ? SOURCE_ORDER.length : i, isDark);
}

const props = defineProps({
	sources: { type: Array, default: () => [] },
});

const sortedSources = computed(() => {
	return [...props.sources].sort((a, b) => getCredits(b) - getCredits(a));
});

const totalCredits = computed(() => {
	return props.sources.reduce((sum, s) => sum + getCredits(s), 0);
});

function getCredits(source) {
	return Math.round(source.credits_consumed || 0);
}

function getPercent(source) {
	if (!totalCredits.value) return 0;
	return Math.round((getCredits(source) / totalCredits.value) * 100);
}

function getColor(sourceName) {
	return sourceColor(sourceName, colors.value.isDark);
}

function formatNumber(val) {
	if (!val && val !== 0) return "0";
	return Number(val).toLocaleString();
}
</script>

<style scoped>
.source-breakdown {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	padding: 1.25rem;
}

.source-list {
	display: flex;
	flex-direction: column;
	gap: 0.875rem;
}

.source-row {
	display: flex;
	align-items: center;
	gap: 0.75rem;
}

.source-info {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	min-width: 140px;
	flex-shrink: 0;
}

.source-dot {
	width: 8px;
	height: 8px;
	border-radius: 50%;
	flex-shrink: 0;
}

.source-name {
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text);
	white-space: nowrap;
}

.source-bar-wrapper {
	flex: 1;
	height: 8px;
	background: var(--ql-bg);
	border-radius: 4px;
	overflow: hidden;
}

.source-bar {
	height: 100%;
	border-radius: 4px;
	transition: width 0.3s ease;
	min-width: 2px;
}

.source-stats {
	display: flex;
	align-items: center;
	gap: 0.25rem;
	min-width: 100px;
	justify-content: flex-end;
	flex-shrink: 0;
}

.source-credits {
	font-size: 0.8125rem;
	font-weight: 600;
	color: var(--ql-text);
}

.source-percent {
	font-size: 0.75rem;
	font-weight: 400;
	color: var(--ql-text-muted);
}

.empty-text {
	font-size: 0.875rem;
	color: var(--ql-text-muted);
}

@media (max-width: 500px) {
	.source-info {
		min-width: 100px;
	}

	.source-stats {
		min-width: 80px;
	}
}
</style>
