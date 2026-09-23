<template>
	<BillingField
		for-id="bd-gstin"
		label="GSTIN"
		label-hint="optional, required for B2B input credit"
		:error="errors.gstin || ''"
	>
		<input
			id="bd-gstin"
			:value="form.gstin"
			type="text"
			class="form-input"
			:class="{ 'input-error': errors.gstin }"
			placeholder="e.g. 29AAHCM7727Q1ZI"
			maxlength="15"
			@input="onInput('gstin', $event)"
			@blur="emit('validate', 'gstin')"
		/>
	</BillingField>

	<BillingField
		for-id="bd-state"
		label="State"
		required
		:error="errors.billing_state || ''"
	>
		<select
			id="bd-state"
			:value="form.billing_state"
			class="form-input"
			:class="{ 'input-error': errors.billing_state }"
			@change="onInput('billing_state', $event)"
		>
			<option value="">Select a state…</option>
			<option v-for="s in INDIAN_STATES" :key="s" :value="s">{{ s }}</option>
		</select>
		<template #hint>
			Your state decides whether GST is charged as CGST+SGST or IGST, and it
			must match the first two digits of your GSTIN.
		</template>
	</BillingField>
</template>

<script setup>
/**
 * The two fields that exist only for Indian customers.
 *
 * They travel together: India Compliance derives the place of supply from the
 * state, and cross-checks it against the GSTIN's first two digits — so a
 * mismatch between them is a single defect, not two.
 *
 * Reads through props and writes through events, so the form state stays
 * owned by the parent alongside every other field.
 */
import BillingField from "./BillingField.vue";
import { INDIAN_STATES } from "@/composables/_billing/billingValidation";

defineProps({
	form: { type: Object, required: true },
	errors: { type: Object, default: () => ({}) },
});

const emit = defineEmits(["update", "validate", "clear"]);

function onInput(field, event) {
	emit("update", field, event.target.value);
	emit("clear", field);
}
</script>
