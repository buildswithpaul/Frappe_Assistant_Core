<template>
	<div class="model-breakdown">
		<div
			v-for="(m, i) in breakdown"
			:key="m.model_id + '-' + i"
			class="breakdown-row"
		>
			<span class="bd-model">{{ shortenModel(m.model_id) }}</span>
			<span class="bd-role" :class="m.role">{{ m.role }}</span>
			<span class="bd-credits">{{ formatCredits(m.credits) }} cr</span>
		</div>
	</div>
</template>

<script setup>
defineProps({
	breakdown: { type: Array, default: () => [] },
});

function shortenModel(modelId) {
	if (!modelId) return "";
	return modelId.replace(/-\d{8}$/, "");
}

function formatCredits(val) {
	if (!val) return "0";
	if (val < 1) return val.toFixed(2);
	return Math.round(val).toLocaleString();
}
</script>

<style scoped>
.model-breakdown {
	margin-top: 0.5rem;
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	overflow: hidden;
	background: var(--ql-bg);
}

.breakdown-row {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.3125rem 0.625rem;
	font-size: 0.6875rem;
	border-bottom: 1px solid var(--ql-border);
}

.breakdown-row:last-child {
	border-bottom: none;
}

.bd-model {
	font-family: monospace;
	color: var(--ql-text);
	flex: 1;
	min-width: 0;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.bd-role {
	text-transform: uppercase;
	font-weight: 600;
	font-size: 0.625rem;
	letter-spacing: 0.02em;
	padding: 0.0625rem 0.3125rem;
	border-radius: 0.1875rem;
	flex-shrink: 0;
}

.bd-role.orchestrator {
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
}

.bd-role.helper {
	background: var(--ql-subtle);
	color: var(--ql-text-secondary);
}

.bd-credits {
	font-weight: 700;
	color: var(--ql-text);
	flex-shrink: 0;
	min-width: 3rem;
	text-align: right;
}
</style>
