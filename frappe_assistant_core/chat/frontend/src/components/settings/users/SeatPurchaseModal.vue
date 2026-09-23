<template>
	<Teleport to="body">
		<div v-if="confirmData" class="modal-overlay" @click.self="$emit('close')">
			<div class="seat-confirm-modal">
				<h3 class="confirm-title">Additional Seat Required</h3>
				<p class="confirm-text">
					{{ isInvite ? "Inviting" : "Adding" }}
					<strong>{{ confirmData.full_name || confirmData.user_id }}</strong> will purchase
					an additional seat on your plan.
				</p>
				<div class="confirm-breakdown">
					<div class="breakdown-row">
						<span>Per-user price</span>
						<span class="breakdown-value"
							>{{ formatAmount(confirmData.perUserPrice) }}/month</span
						>
					</div>
					<div class="breakdown-row">
						<span
							>Prorated ({{ confirmData.daysRemaining }} of
							{{ confirmData.daysInCycle }} days)</span
						>
						<span class="breakdown-value">{{
							formatAmount(confirmData.proratedRate)
						}}</span>
					</div>
					<div
						v-for="c in confirmData.components || []"
						:key="c.name"
						class="breakdown-row"
					>
						<span>{{ c.name }} @ {{ c.rate_percent }}%</span>
						<span class="breakdown-value">{{ formatAmount(c.amount) }}</span>
					</div>
					<div class="breakdown-row total">
						<span>Charge now</span>
						<span class="breakdown-value">{{ formatAmount(confirmData.total) }}</span>
					</div>
					<div v-if="showsCredits" class="breakdown-row credits">
						<span>Credits added now</span>
						<span class="breakdown-value">{{
							formatCredits(confirmData.creditsGranted)
						}}</span>
					</div>
				</div>
				<p v-if="showsCredits" class="confirm-note">
					Credits are prorated with the price. This seat adds
					{{ formatCredits(confirmData.creditsGranted) }} for the rest of this cycle,
					then its full {{ formatCredits(confirmData.creditsPerUser) }} a month from
					your next renewal.
				</p>
				<p class="confirm-note">
					From next month, your renewal will reflect
					{{ confirmData.newSeatCount }} seats.
				</p>
				<HostedCheckoutNotice />

				<div class="confirm-actions">
					<button class="btn-secondary" @click="$emit('close')">Cancel</button>
					<button class="btn-primary" @click="$emit('confirm')" :disabled="processing">
						{{ processingLabel }}
					</button>
				</div>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
import { computed } from "vue";
import HostedCheckoutNotice from "../billing/HostedCheckoutNotice.vue";

const props = defineProps({
	confirmData: { type: Object, default: null },
	processing: { type: Boolean, default: false },
});

defineEmits(["close", "confirm"]);

// Same modal serves add-user and invite; `userRole` on the payload marks an
// invite (see useAddUserFlow), so the copy can read correctly for both.
const isInvite = computed(() => !!props.confirmData?.userRole);

const processingLabel = computed(() => {
	if (props.processing) return isInvite.value ? "Inviting..." : "Adding...";
	return isInvite.value ? "Invite & Purchase Seat" : "Add User & Purchase Seat";
});

// Only when the plan actually carries per-seat credits. A pool plan reports
// 0 (no per-seat allowance) or -1 (unlimited), and neither is a number worth
// putting in front of an admin as "credits added now".
const showsCredits = computed(() => {
	const perUser = props.confirmData?.creditsPerUser;
	return Number(perUser) > 0 && props.confirmData?.creditsGranted != null;
});

const CURRENCY_SYMBOLS = { INR: "₹", USD: "$", EUR: "€", GBP: "£" };

function formatCredits(value) {
	if (value == null) return "—";
	return `${Number(value).toLocaleString()} credits`;
}

function formatAmount(value) {
	if (value == null) return "—";
	const sym = CURRENCY_SYMBOLS[props.confirmData?.currency] || "";
	return `${sym}${Number(value).toLocaleString(undefined, {
		minimumFractionDigits: 2,
		maximumFractionDigits: 2,
	})}`;
}
</script>

<style scoped>
/* Modal Overlay */
.modal-overlay {
	position: fixed;
	inset: 0;
	background: rgba(0, 0, 0, 0.5);
	display: flex;
	align-items: center;
	justify-content: center;
	z-index: 1200;
	padding: 1rem;
}

/* Seat Purchase Confirmation Modal */
.seat-confirm-modal {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	width: 100%;
	max-width: 400px;
	padding: 1.5rem;
	box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}

.confirm-title {
	font-size: 1.0625rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0 0 0.75rem;
}

.confirm-text {
	font-size: 0.875rem;
	color: var(--ql-text);
	margin: 0 0 0.5rem;
	line-height: 1.5;
}

.confirm-breakdown {
	padding: 0.75rem;
	background: var(--ql-subtle);
	border-radius: 0.5rem;
	margin: 0.75rem 0;
}

.breakdown-row {
	display: flex;
	justify-content: space-between;
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
	padding: 0.25rem 0;
}

.breakdown-row.total {
	border-top: 1px solid var(--ql-border);
	margin-top: 0.375rem;
	padding-top: 0.5rem;
	font-weight: 600;
	color: var(--ql-text);
}

/* Entitlement, not money — sits with the charge it is prorated alongside,
   but reads as a secondary line so the total stays the figure that lands. */
.breakdown-row.credits {
	margin-top: 0.25rem;
	color: var(--ql-text);
}

.breakdown-value {
	font-weight: 600;
	color: var(--ql-text);
}

.confirm-note {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	margin: 0 0 1rem;
}

.confirm-actions {
	display: flex;
	gap: 0.75rem;
	justify-content: flex-end;
}

.btn-secondary {
	padding: 0.5rem 1rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
	background: transparent;
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.btn-secondary:hover {
	background: var(--ql-subtle);
}

.btn-primary {
	padding: 0.5rem 1rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: white;
	background: var(--ql-accent);
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.btn-primary:hover:not(:disabled) {
	background: var(--ql-accent-hover);
}

.btn-primary:disabled {
	opacity: 0.6;
	cursor: not-allowed;
}

/* Responsive adjustments */
@media (max-width: 640px) {
	.confirm-actions {
		flex-direction: column;
	}

	.confirm-actions .btn-secondary,
	.confirm-actions .btn-primary {
		width: 100%;
		justify-content: center;
	}
}
</style>
