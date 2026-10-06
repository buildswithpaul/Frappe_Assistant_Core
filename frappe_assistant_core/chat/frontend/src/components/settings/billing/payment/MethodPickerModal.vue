<template>
	<Teleport :to="teleportTarget">
		<div v-if="isOpen" class="modal-overlay" @click.self="$emit('close')">
			<div class="picker-modal">
				<h3>Choose how to pay</h3>

				<p v-if="amountDue" class="due-line">
					You'll be charged
					<strong>{{ formatCurrency(amountDue.amount, amountDue.currency) }}</strong>
					now, and this method will be saved for future renewals.
				</p>
				<p v-else class="due-line">
					We'll charge a small authorization amount and refund it
					automatically.
				</p>

				<button v-if="showUpi" class="method" @click="$emit('select', 'upi')">
					<span class="method-name">UPI Autopay</span>
					<span class="method-hint">Pay from your bank app</span>
				</button>

				<button class="method" @click="$emit('select', 'card')">
					<span class="method-name">Card</span>
					<span class="method-hint">Debit or credit card</span>
				</button>

				<HostedCheckoutNotice />

				<button class="cancel" @click="$emit('close')">Cancel</button>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
import { computed } from "vue";

import HostedCheckoutNotice from "../HostedCheckoutNotice.vue";
import { useTeleportTarget } from "@/composables/useTeleportTarget";

const teleportTarget = useTeleportTarget();

const props = defineProps({
	isOpen: { type: Boolean, default: false },
	amountDue: { type: Object, default: null },
	// The currency the next charge is in; null when it is not known.
	currency: { type: String, default: null },
	formatCurrency: { type: Function, required: true },
});

defineEmits(["select", "close"]);

// UPI Autopay needs an Indian bank account: Razorpay bills India in INR and
// everyone else through card-only USD subscriptions, and the backend refuses
// a UPI request from a customer billed outside India. So UPI is offered only
// when the charge is known to be in INR; an unknown currency offers Card.
const showUpi = computed(() => props.currency === "INR");
</script>

<style scoped>
.modal-overlay {
	position: fixed;
	inset: 0;
	display: flex;
	align-items: center;
	justify-content: center;
	background: rgba(0, 0, 0, 0.5);
	z-index: 1100;
	padding: 1rem;
}

.picker-modal {
	width: min(24rem, calc(100vw - 2rem));
	padding: 1.5rem;
	background: var(--ql-surface, #fff);
	border-radius: 0.75rem;
	box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
}

.picker-modal h3 {
	margin: 0 0 0.5rem;
	font-size: 1.0625rem;
	font-weight: 600;
	color: var(--ql-text);
}

.due-line {
	margin: 0 0 1.25rem;
	font-size: 0.8125rem;
	color: var(--ql-text-secondary);
}

.method {
	display: flex;
	flex-direction: column;
	width: 100%;
	padding: 0.75rem 0.875rem;
	margin-bottom: 0.625rem;
	text-align: left;
	background: none;
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.method:hover {
	border-color: var(--ql-accent);
	background: var(--ql-accent-soft);
}

.method-name {
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
}

.method-hint {
	font-size: 0.75rem;
	color: var(--ql-text-secondary);
}

.cancel {
	width: 100%;
	padding: 0.5rem;
	font-size: 0.8125rem;
	color: var(--ql-text-secondary);
	background: none;
	border: none;
	cursor: pointer;
}

.cancel:hover {
	color: var(--ql-text);
}
</style>
