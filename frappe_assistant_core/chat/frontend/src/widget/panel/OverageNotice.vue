<template>
	<div class="on" data-test="overage" role="status">
		<span>{{ text }}</span>
		<button type="button" class="on-dismiss" data-test="overage-dismiss" :aria-label="t('Dismiss')" @click="$emit('dismiss')">
			✕
		</button>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { t } from "./i18n.js";

const props = defineProps({
	creditBalance: { type: Number, default: 0 },
});
defineEmits(["dismiss"]);

// Whole numbers below 1K, one decimal with a K/M suffix beyond: the old widget's format,
// which differs from the SPA's formatCredits (that rounds 1.5K to 2K).
function formatBalance(num) {
	const n = Number(num) || 0;
	if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
	if (n >= 1000) return (n / 1000).toFixed(1) + "K";
	return Math.round(n).toString();
}

const text = computed(() =>
	t("Your monthly credits are used up — FAC Chat is now drawing on your prepaid credits ({0} left).", [
		formatBalance(props.creditBalance),
	])
);
</script>

<style scoped>
.on {
	display: flex;
	align-items: flex-start;
	gap: 8px;
	margin: 0 12px 8px;
	padding: 8px 12px;
	border: 1px solid var(--ql-border);
	border-radius: 8px;
	background: var(--ql-bg);
	color: var(--ql-text-secondary);
	font-size: 12px;
	line-height: 1.4;
}
.on-dismiss {
	margin-left: auto;
	border: none;
	background: transparent;
	color: var(--ql-text-muted);
	cursor: pointer;
}
</style>
