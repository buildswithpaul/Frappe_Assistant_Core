<template>
	<div class="payment-tab">
		<p v-if="loadingInstrument" class="loading">Loading payment method…</p>

		<!-- Distinct from AutopayCard's own empty state: this means the read
		     itself failed (non-admin, unregistered tenant, AR unreachable),
		     not "no card on file" — those must never look the same. -->
		<template v-else-if="instrumentError">
			<p class="tab-error">{{ instrumentError }}</p>
			<button class="retry-btn" @click="loadInstrument">Retry</button>
		</template>

		<template v-else>
			<!-- Why the last charge failed — the admin may have missed the email.
			     Plain text: the reason is the gateway's own wording. -->
			<div v-if="failureLines" class="failure-notice" role="status">
				<p>
					<strong>{{ failureLines.reason ? "Last payment failed:" : "Your last payment didn't go through." }}</strong>
					<template v-if="failureLines.reason"> {{ failureLines.reason }}</template>
				</p>
				<p v-if="failureLines.retry">{{ failureLines.retry }}</p>
			</div>

			<AutopayCard
				:instrument="instrument"
				:update-mode="updateMode"
				:amount-due="amountDue"
				:can-update="canUpdate"
				:updating="updating"
				:format-currency="formatCurrency"
				@update="onUpdateClicked"
			/>

			<!-- Lands next to the card that owns the button, not scrolled away
			     at the top of the page in BillingBanners. -->
			<p v-if="updateError" class="update-error">{{ updateError }}</p>

			<MethodPickerModal
				:is-open="showPicker"
				:amount-due="amountDue"
				:currency="pickerCurrency"
				:format-currency="formatCurrency"
				@select="onMethodChosen"
				@close="showPicker = false"
			/>
		</template>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";

import { paymentFailureLines } from "../paymentFailureCopy";
import AutopayCard from "./AutopayCard.vue";
import MethodPickerModal from "./MethodPickerModal.vue";

const props = defineProps({
	formatCurrency: { type: Function, required: true },
	paymentMethod: { type: Object, required: true },
});

const {
	instrument,
	updateMode,
	amountDue,
	canUpdate,
	paymentFailure,
	loadingInstrument,
	updating,
	instrumentError,
	updateError,
	billingCurrency,
	loadInstrument,
	updatePaymentMethod,
} = props.paymentMethod;

const showPicker = ref(false);

// `paymentFailure` is optional: a caller built against an older composable
// does not supply the ref.
const failureLines = computed(() => paymentFailureLines(paymentFailure?.value));

// What the next charge will be denominated in — the outstanding invoice's
// own currency when there is one, otherwise the saved instrument's, otherwise
// the one the billing country bills in. Null when none is known, which the
// picker reads as "unknown" and offers Card alone.
const pickerCurrency = computed(
	() =>
		amountDue.value?.currency ||
		instrument.value?.currency ||
		billingCurrency?.value ||
		null
);

// Stripe's portal handles instrument choice itself, so there is nothing to
// pick — go straight there.
function onUpdateClicked() {
	if (updateMode.value === "portal") {
		updatePaymentMethod();
		return;
	}
	showPicker.value = true;
}

function onMethodChosen(method) {
	showPicker.value = false;
	updatePaymentMethod(method);
}

onMounted(loadInstrument);
</script>

<style scoped>
.payment-tab {
	padding-top: 1.25rem;
}

.loading {
	font-size: 0.8125rem;
	color: var(--ql-text-secondary);
}

.tab-error {
	margin: 0 0 0.75rem;
	font-size: 0.8125rem;
	color: var(--ql-danger, #ef4444);
}

.update-error {
	margin: 0.75rem 0 0;
	font-size: 0.8125rem;
	color: var(--ql-danger, #ef4444);
}

.failure-notice {
	margin: 0.75rem 0;
	font-size: 0.8125rem;
	color: var(--ql-danger, #ef4444);
}

.failure-notice p {
	margin: 0;
}

.retry-btn {
	padding: 0.5rem 0.875rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text);
	background: none;
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	cursor: pointer;
}

.retry-btn:hover {
	border-color: var(--ql-accent);
	color: var(--ql-accent);
}
</style>
