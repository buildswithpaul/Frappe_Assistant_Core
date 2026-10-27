<template>
	<div class="my-credits-band">
		<AllowanceCard v-bind="allowance" :label="label" :note="scope.isPersonal ? '' : __('Shared by your workspace')" />
		<p v-if="block" class="at-limit" role="status" data-test="at-limit">
			{{ atLimitText }}
		</p>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { storeToRefs } from "pinia";
import AllowanceCard from "./AllowanceCard.vue";
import { monthAllowance } from "./usageHelpers";
import { useCreditScope } from "@/composables/useCreditScope";
import { useUserStore } from "@/stores/userStore";
import { percentOf } from "@/utils/creditPercent";
import { personalLimitBlock } from "@/utils/personalLimit";
import { __ } from "@/utils/i18n";

const { quotaInfo, myCreditStatus } = storeToRefs(useUserStore());

// The same allowance the top-bar meter measures: a personal cap when one is set, else the pool.
const scope = useCreditScope();

const label = computed(() => (scope.value.isPersonal ? __("Your monthly limit") : __("This month")));

const resetDate = computed(() => (quotaInfo.value ? monthAllowance(quotaInfo.value).resetDate : null));

const allowance = computed(() => {
	// Without a quota snapshot there is no cycle to describe, so say so rather than show zeros.
	const base = quotaInfo.value ? monthAllowance(quotaInfo.value) : { unknown: true, resetDate: null };
	if (!scope.value.isPersonal) return base;
	const { used, total } = scope.value;
	return { ...base, used, total, percent: percentOf(used, total), unlimited: false, unknown: false };
});

const block = computed(() => personalLimitBlock(myCreditStatus.value));

const atLimitText = computed(() =>
	resetDate.value
		? __("You've used your monthly limit. It resets on {0}. Ask a workspace admin to raise it.", [resetDate.value])
		: __("You've used your monthly limit. Ask a workspace admin to raise it."),
);
</script>

<style scoped>
.my-credits-band {
	display: grid;
	gap: 0.75rem;
	max-width: 480px;
	margin-bottom: 1.5rem;
}

.at-limit {
	margin: 0;
	padding: 0.75rem 1rem;
	font-size: 0.8rem;
	color: var(--ql-danger);
	background: var(--ql-surface);
	border: 1px solid var(--ql-danger);
	border-radius: 0.75rem;
}
</style>
