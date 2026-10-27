<template>
	<div class="credits-band">
		<AllowanceCard v-bind="allowance" />
		<ExtraCreditsCard :balance="quota.credit_balance || 0" @buy-credits="emit('buy-credits')" />
		<div v-if="showLimits" class="limit-card" data-test="members-at-limit">
			<div class="card-label">{{ __("Member limits") }}</div>
			<div class="card-value">{{ limitText }}</div>
			<router-link class="manage-link" to="/settings/users">{{ __("Manage limits") }}</router-link>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import AllowanceCard from "./AllowanceCard.vue";
import ExtraCreditsCard from "./ExtraCreditsCard.vue";
import { monthAllowance } from "./usageHelpers";
import { __ } from "@/utils/i18n";

const props = defineProps({
	quota: { type: Object, required: true },
	membersAtLimit: { type: [Number, String], default: null },
});

const emit = defineEmits(["buy-credits"]);

const allowance = computed(() => monthAllowance(props.quota));

const showLimits = computed(() => props.membersAtLimit !== null && Number(props.membersAtLimit) !== 0);

// A string means the list was capped (e.g. "100+"), so it is always plural.
const limitText = computed(() =>
	Number(props.membersAtLimit) === 1 && typeof props.membersAtLimit === "number"
		? __("1 member at their limit")
		: __("{0} members at their limit", [props.membersAtLimit]),
);
</script>

<style scoped>
.credits-band {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
	gap: 1rem;
	margin-bottom: 1.5rem;
}

.limit-card {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	padding: 1.25rem;
}

.card-label {
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.05em;
	margin-bottom: 0.5rem;
}

.card-value {
	font-size: 1.125rem;
	font-weight: 600;
	color: var(--ql-text);
}

.manage-link {
	display: inline-block;
	margin-top: 0.75rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-accent);
}
</style>
