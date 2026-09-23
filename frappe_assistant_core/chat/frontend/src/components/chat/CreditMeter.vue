<template>
	<div v-if="hasQuota" class="credit-meter" :class="toneClass" :title="tooltip">
		<div class="meter-track" aria-hidden="true">
			<div class="meter-fill" :style="{ width: `${clampedPercent}%` }"></div>
		</div>
		<span class="meter-label">{{ label }}</span>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { useUserStore } from "@/stores/userStore";
import { useCreditScope } from "@/composables/useCreditScope";

const userStore = useUserStore();

const quota = computed(() => userStore.quotaInfo);

// A member whose admin capped them is blocked by that cap, never by the team
// pool — so the meter measures whichever allowance actually governs them.
const scope = useCreditScope();

// An unlimited pool reports -1 and has nothing to meter.
const hasQuota = computed(() => scope.value.total > 0);

const clampedPercent = computed(() => {
	const { total, used } = scope.value;
	if (total <= 0) return 0;
	return Math.min(100, Math.max(0, (used / total) * 100));
});

const label = computed(() => `${Math.round(clampedPercent.value)}% used`);

// Amber and red mirror the widget's quota thresholds so the two surfaces
// warn at the same points.
const toneClass = computed(() => {
	if (clampedPercent.value >= 100) return "is-exhausted";
	if (clampedPercent.value >= 90) return "is-critical";
	if (clampedPercent.value >= 80) return "is-warning";
	return "";
});

// The percentage alone can't say *whose* credits it counts, so the tooltip
// names the scope and carries the exact figures.
const tooltip = computed(() => {
	const used = formatCredits(scope.value.used);
	const total = formatCredits(scope.value.total);
	const prefix = scope.value.isPersonal
		? "Your limit — "
		: quota.value?.plan
			? `${quota.value.plan} plan — `
			: "";
	return `${prefix}${used} of ${total} credits used this month. Credits scale with reply length and model tier.`;
});

function formatCredits(value) {
	if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`;
	if (value >= 1000) return `${(value / 1000).toFixed(1)}k`;
	return String(Math.round(value));
}
</script>

<style scoped>
.credit-meter {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.25rem 0.5rem;
	border-radius: 0.375rem;
	cursor: default;
}

.meter-track {
	width: 48px;
	height: 4px;
	border-radius: 999px;
	background: var(--ql-border, #e5e7eb);
	overflow: hidden;
}

.meter-fill {
	height: 100%;
	border-radius: 999px;
	background: var(--ql-accent, #0f766e);
	transition: width 0.4s ease;
}

.meter-label {
	font-size: 0.75rem;
	color: var(--ql-text-muted, #6b7280);
	white-space: nowrap;
}

.is-warning .meter-fill {
	background: #f59e0b;
}

.is-critical .meter-fill,
.is-exhausted .meter-fill {
	background: #dc2626;
}

.is-critical .meter-label,
.is-exhausted .meter-label {
	color: #dc2626;
}

@media (max-width: 640px) {
	.credit-meter {
		display: none;
	}
}
</style>
