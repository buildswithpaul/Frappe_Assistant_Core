<template>
	<div class="my-credits-band">
		<AllowanceCard v-bind="allowance" :label="label" :note="scope.isPersonal ? '' : __('Shared by your workspace')" />
		<p v-if="block" class="notice" role="status" data-test="at-limit">
			{{ atLimitIntro }}
			<router-link v-if="isAdmin" class="notice-link" to="/settings/users" data-test="change-limit">
				{{ __("You can change it under Settings, Users.") }}
			</router-link>
			<template v-else>{{ __("Ask a workspace admin to raise it.") }}</template>
		</p>
		<p v-if="workspaceOut" class="notice" role="status" data-test="workspace-out">
			{{ workspaceOutText }}
			<router-link v-if="isAdmin" class="notice-link" to="/analytics?buy=1" data-test="buy-more">
				{{ __("Buy more credits.") }}
			</router-link>
			<template v-else>{{ __("Ask a workspace admin to add more.") }}</template>
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

const { quotaInfo, myCreditStatus, isAdmin } = storeToRefs(useUserStore());

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

const atLimitIntro = computed(() =>
	resetDate.value
		? __("You've used your monthly limit. It resets on {0}.", [resetDate.value])
		: __("You've used your monthly limit."),
);

// A member on the shared pool is stopped when the workspace's credits and any bought extras are gone.
const workspaceOut = computed(() => {
	const { unlimited, unknown, percent } = allowance.value;
	if (scope.value.isPersonal || unlimited || unknown || percent < 100) return false;
	return !(quotaInfo.value?.credit_balance > 0);
});

const workspaceOutText = computed(() =>
	resetDate.value
		? __("Your workspace has used this month's credits. They reset on {0}.", [resetDate.value])
		: __("Your workspace has used this month's credits."),
);
</script>

<style scoped>
.my-credits-band {
	display: grid;
	gap: 0.75rem;
	margin-bottom: 1.5rem;
}

.notice {
	margin: 0;
	padding: 0.75rem 1rem;
	font-size: 0.8rem;
	color: var(--ql-danger);
	background: var(--ql-surface);
	border: 1px solid var(--ql-danger);
	border-radius: 0.75rem;
}

.notice-link {
	color: var(--ql-accent);
	font-weight: 500;
}
</style>
