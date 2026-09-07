<template>
	<div v-if="attention" class="att">
		<button type="button" class="att-main" @click="$emit('review')">
			<span class="att-icon" aria-hidden="true">⚠️</span>
			<span class="att-text">
				<template v-if="attention.count === 1 && attention.workflowName">
					Overnight: the <strong>{{ attention.workflowName }}</strong> workflow failed
				</template>
				<template v-else-if="attention.count === 1">A workflow run failed recently</template>
				<template v-else>{{ attention.count }} workflow runs failed recently</template>
			</span>
			<span class="att-cta">Review →</span>
		</button>
		<button
			type="button"
			class="att-dismiss"
			aria-label="Dismiss"
			title="Dismiss"
			@click="$emit('dismiss')"
		>
			✕
		</button>
	</div>
</template>

<script setup>
defineProps({ attention: { type: Object, default: null } });
defineEmits(["review", "dismiss"]);
</script>

<style scoped>
.att {
	display: flex; align-items: stretch; gap: 4px; width: 100%;
	background: var(--ql-surface);
	border: 1px solid var(--ql-gold-soft); border-left: 3px solid var(--ql-gold);
	border-radius: 10px;
	transition: border-color 0.15s ease;
}
.att:hover { border-color: var(--ql-gold); }
.att-main {
	display: flex; align-items: center; gap: 9px; flex: 1; min-width: 0;
	background: transparent; border: none;
	padding: 9px 13px;
	font-size: 13px; color: var(--ql-text-secondary);
	text-align: left; cursor: pointer;
}
.att-text { flex: 1; min-width: 0; }
.att-text strong { color: var(--ql-text); font-weight: 600; }
.att-cta { color: var(--ql-accent); font-weight: 600; white-space: nowrap; }
.att-dismiss {
	display: flex; align-items: center; justify-content: center;
	background: transparent; border: none;
	padding: 0 12px;
	font-size: 13px; line-height: 1; color: var(--ql-text-muted);
	cursor: pointer; border-radius: 0 8px 8px 0;
	transition: color 0.15s ease, background 0.15s ease;
}
.att-dismiss:hover { color: var(--ql-text); background: var(--ql-gold-soft); }
</style>
