<template>
	<div class="plans-tab">
		<PlanPicker
			:available-plans="availablePlans"
			:current-plan="currentPlan"
			v-model:billing-cycle="localBillingCycle"
			:upgrading="upgrading"
			:plan-changes-locked="planChangesLocked"
			:has-scheduled-change="hasScheduledChange"
			:get-plan-price="getPlanPrice"
			:get-plan-price-meta="getPlanPriceMeta"
			:get-plan-action-text="getPlanActionText"
			:seat-status="seatStatus"
			@upgrade="$emit('upgrade', $event)"
			@manage-seats="$emit('manage-seats')"
			@manage-subscription="$emit('manage-subscription')"
		/>
	</div>
</template>

<script setup>
import { computed } from "vue";
import PlanPicker from "./PlanPicker.vue";

const props = defineProps({
	availablePlans: { type: Array, default: () => [] },
	currentPlan: { type: String, required: true },
	billingCycle: { type: String, default: "monthly" },
	upgrading: { type: Boolean, default: false },
	planChangesLocked: { type: Boolean, default: false },
	hasScheduledChange: { type: Boolean, default: false },
	getPlanPrice: { type: Function, required: true },
	getPlanPriceMeta: { type: Function, required: true },
	getPlanActionText: { type: Function, required: true },
	seatStatus: { type: Object, default: null },
});

const emit = defineEmits([
	"upgrade",
	"update:billingCycle",
	"manage-seats",
	"manage-subscription",
]);

const localBillingCycle = computed({
	get: () => props.billingCycle,
	set: (v) => emit("update:billingCycle", v),
});
</script>

<style scoped>
.plans-tab {
	padding-top: 1.5rem;
}
</style>
