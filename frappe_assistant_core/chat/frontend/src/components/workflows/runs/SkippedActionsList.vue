<template>
	<div v-if="items.length" class="skipped">
		<p class="skipped-title">{{ __("Skipped actions") }}</p>
		<ul class="skipped-list">
			<li v-for="(item, i) in items" :key="i">
				<strong>{{ labelFor(item.node_id) }}</strong>
				<code>{{ item.tool }}</code>
				<span class="skipped-reason">{{ item.reason }}</span>
			</li>
		</ul>
		<p class="skipped-hint">
			{{
				__(
					"Set these tools to Always allow for the runtime user in Settings → Connections, then run again."
				)
			}}
		</p>
	</div>
</template>

<script setup>
import { __ } from "@/utils/i18n";

const props = defineProps({
	items: { type: Array, default: () => [] },
	nodeRuns: { type: Array, default: () => [] },
});

function labelFor(nodeId) {
	return props.nodeRuns.find((n) => n.node_id === nodeId)?.node_label || nodeId || __("A step");
}
</script>

<style scoped>
.skipped {
	margin: 0.5rem 0;
	padding: 0.5rem 0.625rem;
	font-size: 0.75rem;
	background: color-mix(in srgb, var(--ql-warning) 12%, transparent);
	border-left: 3px solid var(--ql-warning);
	border-radius: var(--ql-radius-sm);
}
.skipped-title {
	font-weight: 600;
	color: var(--ql-text);
	margin-bottom: 0.25rem;
}
.skipped-list li {
	display: flex;
	flex-wrap: wrap;
	gap: 0.375rem;
	margin-bottom: 0.25rem;
	color: var(--ql-text);
}
.skipped-list code {
	font-family: var(--ql-font-mono);
}
.skipped-reason,
.skipped-hint {
	color: var(--ql-text-secondary);
}
</style>
