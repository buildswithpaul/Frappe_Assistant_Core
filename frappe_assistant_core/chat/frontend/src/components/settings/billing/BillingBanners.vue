<template>
	<!-- Verification Banner -->
	<div
		v-if="verificationMessage"
		class="verification-banner"
		:class="verificationSuccess ? 'success' : 'error'"
	>
		<div class="banner-text">
			<span>{{ verificationMessage }}</span>
			<a
				v-if="verificationSuccess && invoiceInfo?.pdf_url"
				:href="invoiceInfo.pdf_url"
				target="_blank"
				rel="noopener noreferrer"
				class="receipt-link"
				>View Receipt</a
			>
		</div>
		<button
			class="dismiss-btn"
			@click="$emit('dismiss-verification')"
			aria-label="Dismiss verification banner"
		>
			<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M6 18L18 6M6 6l12 12"
				/>
			</svg>
		</button>
	</div>

	<!-- Cancel-at-period-end Warning -->
	<div v-if="cancelAtPeriodEnd" class="cancel-banner">
		<svg class="banner-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<path
				stroke-linecap="round"
				stroke-linejoin="round"
				stroke-width="2"
				d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
			/>
		</svg>
		<div class="banner-content">
			<p>
				<strong>Cancellation scheduled.</strong>
				<span v-if="periodEndDate">
					Your plan stays active until {{ periodEndDate }}. After that you'll move to the
					Free plan and won't be charged again.
				</span>
				<span v-else>
					Your plan stays active until the end of the current billing period. After that
					you'll move to the Free plan and won't be charged again.
				</span>
			</p>
			<button class="reactivate-btn" @click="$emit('reactivate')" :disabled="reactivating">
				{{ reactivating ? "Reactivating..." : "Keep my plan" }}
			</button>
		</div>
	</div>

	<!-- Scheduled Plan Change Banner -->
	<div v-if="hasScheduledChange && !cancelAtPeriodEnd" class="scheduled-change-banner">
		<svg class="banner-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<path
				stroke-linecap="round"
				stroke-linejoin="round"
				stroke-width="2"
				d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
			/>
		</svg>
		<div class="banner-content">
			<p>{{ scheduledChangeMessage }}</p>
			<button
				class="cancel-change-btn"
				@click="$emit('cancel-scheduled-change')"
				:disabled="cancelling"
			>
				{{ cancelling ? "Cancelling..." : "Keep Current Plan" }}
			</button>
		</div>
	</div>

	<!-- Mandate Re-authorization Banner -->
	<!-- Surfaced when the renewal cron flagged needs_mandate_reauth — the
	     projected next-cycle debit exceeds the saved Razorpay mandate's
	     per-debit cap (UPI Autopay's NPCI ₹1,00,000 ceiling), or the bank
	     cancelled the saved token. The button calls `reauthorize_mandate`
	     to mint a fresh token without changing plans. -->
	<div v-if="needsMandateReauth" class="reauth-banner">
		<svg class="banner-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<path
				stroke-linecap="round"
				stroke-linejoin="round"
				stroke-width="2"
				d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"
			/>
		</svg>
		<div class="banner-content">
			<p>
				<strong>Re-authorize your payment method.</strong>
				Your team has grown beyond what the saved mandate authorizes. Re-authorize to
				continue automatic billing for renewals.
			</p>
			<button
				class="reauth-btn"
				@click="$emit('reauthorize-mandate')"
				:disabled="reauthorizing"
			>
				{{ reauthorizing ? "Opening checkout…" : "Re-authorize" }}
			</button>
		</div>
	</div>

	<!-- Payment Failure Banner -->
	<div v-if="paymentFailed" class="payment-failed-banner">
		<svg class="banner-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<path
				stroke-linecap="round"
				stroke-linejoin="round"
				stroke-width="2"
				d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
			/>
		</svg>
		<div class="banner-content">
			<p>
				<strong>Payment failed.</strong> Please update your payment method to avoid service
				interruption.
			</p>
			<p class="grace-info" v-if="graceDaysRemaining > 0">
				{{ graceDaysRemaining }} days remaining in grace period.
			</p>
			<button class="update-payment-btn" @click="$emit('manage-payment')">
				Update Payment Method
			</button>
		</div>
	</div>
</template>

<script setup>
defineProps({
	verificationMessage: { type: String, default: null },
	verificationSuccess: { type: Boolean, default: false },
	invoiceInfo: { type: Object, default: null },
	cancelAtPeriodEnd: { type: Boolean, default: false },
	periodEndDate: { type: String, default: null },
	reactivating: { type: Boolean, default: false },
	hasScheduledChange: { type: Boolean, default: false },
	scheduledChangeMessage: { type: String, default: "" },
	cancelling: { type: Boolean, default: false },
	paymentFailed: { type: Boolean, default: false },
	graceDaysRemaining: { type: Number, default: 0 },
	needsMandateReauth: { type: Boolean, default: false },
	reauthorizing: { type: Boolean, default: false },
});

defineEmits([
	"dismiss-verification",
	"reactivate",
	"cancel-scheduled-change",
	"manage-payment",
	"reauthorize-mandate",
]);
</script>

<style scoped>
/* Verification Banner */
.verification-banner {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 0.75rem 1rem;
	border-radius: 0.5rem;
	margin-bottom: 1rem;
	font-size: 0.875rem;
	word-break: break-word;
	overflow-wrap: anywhere;
}

.verification-banner .banner-text {
	display: flex;
	align-items: center;
	gap: 0.75rem;
	flex: 1;
	min-width: 0;
}

.receipt-link {
	white-space: nowrap;
	font-weight: 500;
	text-decoration: underline;
	opacity: 0.9;
}

.receipt-link:hover {
	opacity: 1;
}

.verification-banner.success .receipt-link {
	color: var(--ql-success, #22c55e);
}

.verification-banner.success {
	background: rgba(34, 197, 94, 0.1);
	color: var(--ql-success, #22c55e);
	border: 1px solid rgba(34, 197, 94, 0.2);
}

.verification-banner.error {
	background: rgba(239, 68, 68, 0.1);
	color: var(--ql-danger, #ef4444);
	border: 1px solid rgba(239, 68, 68, 0.2);
}

.dismiss-btn {
	padding: 0.25rem;
	background: none;
	border: none;
	cursor: pointer;
	color: inherit;
	opacity: 0.7;
}

.dismiss-btn:hover {
	opacity: 1;
}

/* Cancel Banner */
.cancel-banner {
	display: flex;
	gap: 0.75rem;
	padding: 1rem;
	background: rgba(245, 158, 11, 0.1);
	border: 1px solid rgba(245, 158, 11, 0.2);
	border-radius: 0.5rem;
	margin-bottom: 1rem;
}

.banner-icon {
	width: 1.25rem;
	height: 1.25rem;
	color: #f59e0b;
	flex-shrink: 0;
	margin-top: 0.125rem;
}

.banner-content p {
	font-size: 0.875rem;
	color: var(--ql-text);
	margin-bottom: 0.5rem;
}

.reactivate-btn {
	padding: 0.375rem 0.75rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: white;
	background: #f59e0b;
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
}

.reactivate-btn:hover:not(:disabled) {
	background: #d97706;
}

.reactivate-btn:disabled {
	opacity: 0.6;
	cursor: not-allowed;
}

/* Scheduled Change Banner */
.scheduled-change-banner {
	display: flex;
	gap: 0.75rem;
	padding: 1rem;
	background: var(--ql-accent-soft);
	border: 1px solid rgba(15, 110, 92, 0.3);
	border-radius: 0.5rem;
	margin-bottom: 1rem;
}

.scheduled-change-banner .banner-icon {
	color: var(--ql-accent);
}

.cancel-change-btn {
	padding: 0.375rem 0.75rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-accent);
	background: transparent;
	border: 1px solid var(--ql-accent);
	border-radius: 0.375rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.cancel-change-btn:hover:not(:disabled) {
	background: var(--ql-accent-soft);
}

.cancel-change-btn:disabled {
	opacity: 0.6;
	cursor: not-allowed;
}

/* Re-auth Banner — same warning palette as cancel/scheduled, distinct
   from payment-failed (which uses the destructive red). Re-auth is a
   "your action needed soon" not "you're already broken" state. */
.reauth-banner {
	display: flex;
	gap: 0.75rem;
	padding: 1rem;
	background: rgba(245, 158, 11, 0.1);
	border: 1px solid rgba(245, 158, 11, 0.3);
	border-radius: 0.5rem;
	margin-bottom: 1rem;
}

.reauth-banner .banner-icon {
	color: #f59e0b;
	flex-shrink: 0;
	width: 1.25rem;
	height: 1.25rem;
}

.reauth-banner .banner-content {
	flex: 1;
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
}

.reauth-banner .banner-content p {
	margin: 0;
	font-size: 0.8125rem;
	color: var(--ql-text);
}

.reauth-btn {
	align-self: flex-start;
	padding: 0.375rem 0.75rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: white;
	background: #f59e0b;
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
}

.reauth-btn:hover:not(:disabled) {
	background: #d97706;
}

.reauth-btn:disabled {
	opacity: 0.6;
	cursor: not-allowed;
}

/* Payment Failure Banner */
.payment-failed-banner {
	display: flex;
	align-items: flex-start;
	gap: 0.75rem;
	padding: 0.875rem 1rem;
	background: #fef2f2;
	border: 1px solid #fecaca;
	border-radius: 0.5rem;
	margin-bottom: 1.25rem;
}

.payment-failed-banner .banner-icon {
	width: 1.25rem;
	height: 1.25rem;
	color: var(--ql-danger, #ef4444);
	flex-shrink: 0;
	margin-top: 0.125rem;
}

.payment-failed-banner .banner-content p {
	margin: 0 0 0.5rem;
	font-size: 0.8125rem;
	color: #991b1b;
	line-height: 1.5;
}

.payment-failed-banner .grace-info {
	font-size: 0.75rem;
	color: #b91c1c;
	font-weight: 500;
}

.update-payment-btn {
	padding: 0.375rem 0.75rem;
	font-size: 0.75rem;
	font-weight: 500;
	color: white;
	background: var(--ql-danger, #ef4444);
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
}

.update-payment-btn:hover {
	opacity: 0.9;
}

.w-4 {
	width: 1rem;
	height: 1rem;
}
</style>
