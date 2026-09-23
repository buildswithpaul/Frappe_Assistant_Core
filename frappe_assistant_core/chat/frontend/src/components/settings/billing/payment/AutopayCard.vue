<template>
	<div class="autopay-card">
		<div v-if="instrument" class="instrument">
			<div class="instrument-head">
				<span class="method-label">{{ instrument.label }}</span>
				<span class="status-pill" :class="statusClass">{{ statusText }}</span>
			</div>

			<p class="display">{{ instrument.display }}</p>

			<dl v-if="instrument.card?.expiry || instrument.next_charge_date || instrument.max_amount" class="facts">
				<div v-if="instrument.card?.expiry" class="fact">
					<dt>Expires</dt>
					<dd>{{ instrument.card.expiry }}</dd>
				</div>
				<div v-if="instrument.next_charge_date" class="fact">
					<dt>Next charge</dt>
					<dd>{{ instrument.next_charge_date }}</dd>
				</div>
				<div v-if="instrument.max_amount" class="fact">
					<dt>Authorized up to</dt>
					<dd>
						{{ formatCurrency(instrument.max_amount, instrument.currency) }}
						per charge
					</dd>
				</div>
			</dl>
		</div>

		<p v-else class="empty">{{ emptyText }}</p>

		<!-- Settling clears the debt; a swap does not. A suspended tenant who
		     only swaps their card is still suspended, and saying so here is
		     the difference between "correct" and "looks broken". -->
		<p v-if="showSuspendedNote" class="note">
			Your account stays suspended until the outstanding payment clears.
			Updating the method alone won't lift it.
		</p>

		<div v-if="updateMode === 'settle' && amountDue" class="due">
			<span class="due-label">Outstanding</span>
			<strong>{{ formatCurrency(amountDue.amount, amountDue.currency) }}</strong>
		</div>

		<button class="update-btn" :disabled="updating || !canUpdate" @click="$emit('update')">
			{{ buttonText }}
		</button>

		<p v-if="finePrint" class="fine-print">{{ finePrint }}</p>
	</div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
	instrument: { type: Object, default: null },
	updateMode: { type: String, default: "swap" },
	amountDue: { type: Object, default: null },
	// False for a tenant on neither gateway (no payment_gateway set — e.g.
	// Free plan) — the backend would only refuse the click, so disable it.
	canUpdate: { type: Boolean, default: true },
	updating: { type: Boolean, default: false },
	formatCurrency: { type: Function, required: true },
});

defineEmits(["update"]);

// `status` is opaque, gateway-specific display text (Razorpay mandate
// states vs Stripe subscription states share no vocabulary), so it is
// never used to decide the pill's color. `needs_reauth` and `suspended`
// are the two signals the backend normalizes to mean the same thing on
// both gateways — those drive state, `status` is only ever rendered as text.
const statusText = computed(() => {
	if (!props.instrument) return "";
	if (props.instrument.needs_reauth) return "Needs re-authorization";
	if (props.instrument.suspended) return "Account suspended";
	return props.instrument.status;
});

// There is no signal in the payload that positively confirms an instrument
// is healthy — only two that positively confirm a problem. So the pill
// never claims "ok" (a green, success-coded promise we can't back up): it
// is either a known "warn" or a neutral, unclaimed default. A Razorpay
// mandate stuck at "Failed"/"Expired"/"Cancelled"/"Superseded", or a
// Stripe subscription at "PastDue", falls through to neutral rather than
// rendering a false-positive success pill next to failure text.
const statusClass = computed(() => {
	if (!props.instrument) return "";
	return props.instrument.needs_reauth || props.instrument.suspended ? "warn" : "neutral";
});

const showSuspendedNote = computed(
	() => !!props.instrument?.suspended && props.updateMode !== "settle"
);

// The empty state has to name the same next step the button does — "choose
// a plan" beside "Manage in payment portal" is two contradictory
// instructions. Only a tenant with no gateway at all really has to pick a
// plan first.
const emptyText = computed(() => {
	if (!props.canUpdate) {
		return "No payment method is saved yet. Choose a plan to set one up.";
	}
	if (props.updateMode === "portal") {
		return "No payment method is saved yet. Add one in the payment portal.";
	}
	if (props.updateMode === "settle") {
		return "No payment method is saved yet. Paying the outstanding amount below saves one for future renewals.";
	}
	return "No payment method is saved yet. Add one to keep renewals running automatically.";
});

const buttonText = computed(() => {
	if (props.updating) return "Opening…";
	if (props.updateMode === "settle") return "Pay now with a new method";
	if (props.updateMode === "portal") return "Manage in payment portal";
	return props.instrument ? "Change payment method" : "Add a payment method";
});

const finePrint = computed(() => {
	if (!props.canUpdate) {
		return "Automatic payment updates aren't available for this account yet.";
	}
	if (props.updateMode === "settle") {
		return "Pays the outstanding amount and saves this method for future renewals.";
	}
	if (props.updateMode === "portal") return "";
	return "A small authorization charge is refunded automatically.";
});
</script>

<style scoped>
.autopay-card {
	padding: 1.25rem;
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
}

.instrument-head {
	display: flex;
	align-items: center;
	gap: 0.625rem;
	margin-bottom: 0.375rem;
}

.method-label {
	font-size: 0.75rem;
	font-weight: 600;
	letter-spacing: 0.04em;
	text-transform: uppercase;
	color: var(--ql-text-secondary);
}

.status-pill {
	padding: 0.125rem 0.5rem;
	font-size: 0.6875rem;
	font-weight: 500;
	border-radius: 999px;
}

.status-pill.neutral {
	color: var(--ql-text-secondary);
	background: var(--ql-subtle);
}

.status-pill.warn {
	color: var(--ql-warning, #f59e0b);
	background: rgba(245, 158, 11, 0.12);
}

.display {
	margin: 0 0 0.875rem;
	font-size: 1.0625rem;
	font-weight: 500;
	color: var(--ql-text);
}

.facts {
	display: flex;
	flex-wrap: wrap;
	gap: 1.5rem;
	margin: 0 0 1rem;
}

.fact dt {
	font-size: 0.6875rem;
	color: var(--ql-text-secondary);
	margin-bottom: 0.125rem;
}

.fact dd {
	margin: 0;
	font-size: 0.8125rem;
	color: var(--ql-text);
}

.empty,
.note {
	margin: 0 0 1rem;
	font-size: 0.8125rem;
	color: var(--ql-text-secondary);
}

.note {
	padding: 0.625rem 0.75rem;
	border-radius: 0.375rem;
	background: rgba(245, 158, 11, 0.1);
	color: var(--ql-warning);
}

.due {
	display: flex;
	align-items: baseline;
	justify-content: space-between;
	padding: 0.75rem;
	margin-bottom: 1rem;
	border-radius: 0.375rem;
	background: rgba(239, 68, 68, 0.08);
}

.due-label {
	font-size: 0.75rem;
	color: var(--ql-text-secondary);
}

.update-btn {
	padding: 0.5rem 0.875rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: white;
	background: var(--ql-accent);
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
}

.update-btn:hover:not(:disabled) {
	background: var(--ql-accent-hover);
}

.update-btn:disabled {
	opacity: 0.6;
	cursor: not-allowed;
}

.fine-print {
	margin: 0.5rem 0 0;
	font-size: 0.75rem;
	color: var(--ql-text-secondary);
}
</style>
