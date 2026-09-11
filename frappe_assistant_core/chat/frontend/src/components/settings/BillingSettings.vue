<template>
	<div class="billing-settings">
		<!-- Billing Not Available -->
		<div v-if="!userStore.billingEnabled" class="billing-unavailable">
			<div class="unavailable-icon">
				<svg class="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="1.5"
						d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
					/>
				</svg>
			</div>
			<h3>Billing Not Available</h3>
			<p>Billing features are not enabled on this FAC Cloud instance.</p>
			<p class="hint">Contact your administrator for subscription management.</p>
		</div>

		<!-- Loading State -->
		<div v-else-if="loading" class="loading-state">
			<div class="loading-spinner"></div>
			<p>Loading billing information...</p>
		</div>

		<!-- Error State -->
		<div v-else-if="error" class="error-state">
			<svg class="error-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
				/>
			</svg>
			<p>{{ error }}</p>
			<button class="retry-btn" @click="loadData">Retry</button>
		</div>

		<!-- Non-Admin View -->
		<NonAdminBillingCard
			v-else-if="!isAdmin"
			:current-plan="currentPlan"
			:quota="quota"
			:credits-percentage="creditsPercentage"
			:usage-bar-color="usageBarColor"
		/>

		<!-- Admin View -->
		<template v-else>
			<BillingBanners
				:verification-message="verificationMessage"
				:verification-success="verificationSuccess"
				:invoice-info="invoiceInfo"
				:cancel-at-period-end="cancelAtPeriodEnd"
				:period-end-date="periodEndDate"
				:reactivating="reactivating"
				:has-scheduled-change="hasScheduledChange"
				:scheduled-change-message="scheduledChangeMessage"
				:cancelling="cancelling"
				:payment-failed="paymentFailed"
				:grace-days-remaining="graceDaysRemaining"
				:needs-mandate-reauth="needsMandateReauth"
				:reauthorizing="reauthorizing"
				@dismiss-verification="dismissVerification"
				@reactivate="handleReactivate"
				@cancel-scheduled-change="handleCancelScheduledChange"
				@manage-payment="goToPaymentMethod"
				@reauthorize-mandate="handleReauthorizeMandate"
			/>

			<ExpiringCreditsBanner />

			<!-- Hero: Plan + Usage -->
			<BillingHero
				:current-plan="currentPlan"
				:subscription="subscription"
				:quota="quota"
				:credits-percentage="creditsPercentage"
				:usage-bar-color="usageBarColor"
				:usage-reset-date="usageResetDate"
				:cancel-at-period-end="cancelAtPeriodEnd"
				:period-end-date="periodEndDate"
				@change-plan="activeTab = 'plans'"
				@buy-credits="openCreditPurchase"
			/>

			<!-- Plain-language pricing, next to the usage it explains -->
			<CreditExplainer />

			<!-- Tabs -->
			<BillingTabs v-model="activeTab" />

			<!-- Tab Panels -->
			<PlansTab
				v-if="activeTab === 'plans'"
				:available-plans="availablePlans"
				:current-plan="currentPlan"
				:billing-cycle="billingCycle"
				:upgrading="upgrading"
				:plan-changes-locked="planChangesLocked"
				:has-scheduled-change="hasScheduledChange"
				:get-plan-price="getPlanPrice"
				:get-plan-price-meta="getPlanPriceMeta"
				:get-plan-action-text="getPlanActionText"
				:seat-status="seatStatus"
				@upgrade="handleUpgrade"
				@update:billing-cycle="billingCycle = $event"
				@manage-seats="router.push({ name: 'settings-users' })"
				@manage-subscription="activeTab = 'settings'"
			/>

			<template v-if="activeTab === 'credits'">
				<PrepaidCreditsCard
					:credit-balance="creditBalance"
					:transactions="creditTransactions"
					:next-expiry="creditNextExpiry"
					@buy-credits="openCreditPurchase"
				/>
				<UsageChart />
			</template>

			<BillingDetailsForm
				v-if="activeTab === 'details'"
				:gate-message="billingDetailsGateMessage"
				@saved="handleBillingDetailsSaved"
			/>

			<PaymentMethodTab
				v-if="activeTab === 'payment'"
				:format-currency="formatCurrency"
				:payment-method="paymentMethod"
			/>

			<InvoicesTab
				v-if="activeTab === 'invoices'"
				:invoices="invoices"
				:upcoming-invoice="upcomingInvoice"
				:format-currency="formatCurrency"
				:format-invoice-date="formatInvoiceDate"
				:format-status="formatStatus"
			/>

			<SettingsTab
				v-if="activeTab === 'settings'"
				:cancelling="cancelling"
				:show-danger-zone="currentPlan.toLowerCase() !== 'free' && !cancelAtPeriodEnd"
				:referral="referral"
				@manage-payment="goToPaymentMethod"
				@cancel="requestCancel"
			/>
		</template>

		<!-- Modals -->
		<GatewaySelectionModal
			:is-open="showGatewayModal"
			:gateways="availableGateways"
			:plan-name="selectedPlanForUpgrade?.display_name || selectedPlanForUpgrade?.name || ''"
			:plan-id="selectedPlanForUpgrade?.id || selectedPlanForUpgrade?.name || ''"
			:billing-cycle="billingCycle"
			:is-loading="loadingGateways"
			:error="gatewayError"
			:is-processing="upgrading"
			:billing-name="billingNameForCheckout"
			:billing-email="billingEmailForCheckout"
			:applied-promo="appliedPromo"
			:promo-error="promoError"
			:validating-promo="validatingPromo"
			@close="closeGatewayModal"
			@select="proceedWithGateway"
			@edit-billing-details="onEditBillingDetails"
			@validate-promo="validatePromo"
			@remove-promo="removePromo"
		/>

		<CreditPurchaseModal
			:is-open="showCreditPurchase"
			:gateways="availableGateways"
			:is-processing="purchasingCredits"
			@close="showCreditPurchase = false"
			@purchase="handleCreditPurchase"
		/>

		<ConfirmSubscriptionModal
			:plan="pendingConfirmPlan"
			:price-meta="confirmPriceMeta"
			:billing-cycle="billingCycle"
			:billing-details="billingDetails"
			:authorizing="upgrading"
			@confirm="confirmAndCheckout"
			@cancel="cancelConfirmSubscription"
			@edit-billing="onEditBillingFromConfirm"
		/>

		<DowngradeConfirmModal
			:is-open="showDowngradeConfirm"
			:processing="upgrading"
			@cancel="showDowngradeConfirm = false"
			@confirm="confirmDowngradeToFree"
		/>

		<ConfirmModal
			:open="showCancelConfirm"
			title="Cancel your subscription?"
			:message="cancelConfirmMessage"
			:warning="cancelConfirmWarning"
			confirm-label="Cancel subscription"
			cancel-label="Keep subscription"
			processing-label="Cancelling..."
			:destructive="true"
			:processing="cancelling"
			@confirm="handleCancel"
			@cancel="dismissCancelConfirm"
		/>
	</div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";
import { useUserStore } from "../../stores/userStore";
import { useBillingData } from "@/composables/useBillingData";
import { usePaymentMethod } from "@/composables/usePaymentMethod";
import GatewaySelectionModal from "./GatewaySelectionModal.vue";
import CreditPurchaseModal from "./CreditPurchaseModal.vue";
import PrepaidCreditsCard from "./billing/PrepaidCreditsCard.vue";
import ExpiringCreditsBanner from "./billing/ExpiringCreditsBanner.vue";
import UsageChart from "./billing/UsageChart.vue";
import BillingBanners from "./billing/BillingBanners.vue";
import BillingHero from "./billing/BillingHero.vue";
import BillingTabs from "./billing/BillingTabs.vue";
import CreditExplainer from "./billing/CreditExplainer.vue";
import PlansTab from "./billing/PlansTab.vue";
import InvoicesTab from "./billing/InvoicesTab.vue";
import SettingsTab from "./billing/SettingsTab.vue";
import BillingDetailsForm from "./billing/BillingDetailsForm.vue";
import PaymentMethodTab from "./billing/payment/PaymentMethodTab.vue";
import ConfirmSubscriptionModal from "./billing/ConfirmSubscriptionModal.vue";
import NonAdminBillingCard from "./billing/NonAdminBillingCard.vue";
import DowngradeConfirmModal from "./billing/DowngradeConfirmModal.vue";
import ConfirmModal from "@/components/common/ConfirmModal.vue";

const userStore = useUserStore();
const router = useRouter();
const activeTab = ref("plans");

/**
 * Seat counts for the per-user plan cards, so a Team price is shown against
 * the seats it is actually billed for. Stays null on failure: the card then
 * quotes the seat minimum, which is true for everyone, instead of a count we
 * could not read.
 */
const seatStatus = ref(null);

async function loadSeatStatus() {
	try {
		const result = await api.users.getLimitStatus();
		seatStatus.value = result?.error ? null : result;
	} catch (e) {
		logger.error("[FACO] Seat status unavailable", e);
		seatStatus.value = null;
	}
}

const {
	// State
	loading,
	error,
	verificationMessage,
	verificationSuccess,
	invoiceInfo,
	availablePlans,
	invoices,
	upcomingInvoice,
	billingCycle,
	upgrading,
	cancelling,
	showGatewayModal,
	availableGateways,
	selectedPlanForUpgrade,
	loadingGateways,
	gatewayError,
	reactivating,
	billingDetails,
	showDowngradeConfirm,
	showCancelConfirm,
	showCreditPurchase,
	purchasingCredits,
	creditBalance,
	creditTransactions,
	creditNextExpiry,
	appliedPromo,
	promoError,
	validatingPromo,
	billingDetailsGateMessage,
	pendingPlanAfterDetails,
	pendingConfirmPlan,

	// Computed
	isAdmin,
	quota,
	subscription,
	currentPlan,
	cancelAtPeriodEnd,
	planChangesLocked,
	periodEndDate,
	referral,
	paymentFailed,
	graceDaysRemaining,
	needsMandateReauth,
	reauthorizing,
	hasScheduledChange,
	scheduledChangeMessage,
	creditsPercentage,
	usageBarColor,
	usageResetDate,

	// Formatters
	formatCurrency,
	formatInvoiceDate,
	formatStatus,
	getPlanPrice,
	getPlanPriceMeta,
	getPlanActionText,

	// Actions
	loadData,
	openCreditPurchase,
	handleCreditPurchase,
	handleUpgrade,
	confirmAndCheckout,
	cancelConfirmSubscription,
	closeGatewayModal,
	proceedWithGateway,
	requestCancel,
	dismissCancelConfirm,
	handleCancel,
	handleReactivate,
	handleReauthorizeMandate,
	confirmDowngradeToFree,
	handleCancelScheduledChange,
	dismissVerification,
	validatePromo,
	removePromo,
	handleBillingDetailsSaved: onBillingDetailsSaved,
} = useBillingData();

// Reads and changes the instrument that pays for the subscription. Kept
// separate from useBillingData — it owns its own load/updating state and
// is only consumed by the Payment Method tab.
const paymentMethod = usePaymentMethod({
	verificationMessage,
	verificationSuccess,
	invoiceInfo,
	closeGatewayModal,
	loadData,
	billingDetails,
});

const cancelConfirmMessage = computed(() => {
	if (periodEndDate.value) {
		return `You'll keep full access to your current plan until ${periodEndDate.value}. No further charges will be made.`;
	}
	return "You'll keep full access until the end of your current billing period. No further charges will be made.";
});

const cancelConfirmWarning =
	"After that date your account moves to the Free plan with the Free credit quota. You can reactivate anytime before then.";

// Billing identity is saved on the ERPNext Customer via the Billing
// Details tab. The gateway modal reads these from `billingDetails` and
// just displays them — the form that used to live inside the modal has
// been removed now that the gate ensures they're always complete.
const billingEmailForCheckout = computed(() => billingDetails.value?.billing_email || "");
const billingNameForCheckout = computed(() => {
	const email = billingDetails.value?.billing_email || "";
	return email.split("@")[0] || "";
});

function onEditBillingDetails() {
	closeGatewayModal();
	activeTab.value = "details";
}

// Both the failed-payment banner and the Settings tab used to wire
// @manage-payment to a handler that — on Razorpay — minted a live
// replacement mandate and superseded any checkout the user had open in
// another tab, purely to then tell them to open this tab. Just open it.
function goToPaymentMethod() {
	activeTab.value = "payment";
}

// Modal-side currency-aware pricing for the active confirm step. Resolves
// every render so the billing-cycle toggle in the Plans tab stays in sync.
const confirmPriceMeta = computed(() =>
	pendingConfirmPlan.value ? getPlanPriceMeta(pendingConfirmPlan.value) : null
);

function onEditBillingFromConfirm() {
	cancelConfirmSubscription();
	activeTab.value = "details";
}

// When `handleUpgrade` gates on missing billing details, it stashes the
// plan on `pendingPlanAfterDetails`; we watch it and switch to the
// details tab so the banner + form are in front of the user.
watch(pendingPlanAfterDetails, (plan) => {
	if (plan) activeTab.value = "details";
});

async function handleBillingDetailsSaved(payload) {
	await onBillingDetailsSaved(payload);
	// If the user originally clicked Subscribe on a plan, the saved handler
	// re-runs the upgrade and the gateway modal opens — we don't need to
	// switch tabs here. If there was no pending plan, stay on details.
}

onMounted(() => {
	loadData();
	loadSeatStatus();
});
</script>

<style scoped>
.billing-settings {
	width: 100%;
	max-width: 1100px;
}

/* Billing Unavailable */
.billing-unavailable {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 3rem 1.5rem;
	text-align: center;
}

.unavailable-icon {
	color: var(--ql-text-muted);
	margin-bottom: 1rem;
}

.unavailable-icon svg {
	width: 3rem;
	height: 3rem;
}

.billing-unavailable h3 {
	font-size: 1.125rem;
	font-weight: 600;
	color: var(--ql-text);
	margin-bottom: 0.5rem;
}

.billing-unavailable p {
	color: var(--ql-text-muted);
	font-size: 0.875rem;
}

.billing-unavailable .hint {
	margin-top: 1rem;
	font-size: 0.8125rem;
}

/* Loading & Error */
.loading-state {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 1rem;
	padding: 3rem;
	color: var(--ql-text-muted);
}

.loading-spinner {
	width: 2rem;
	height: 2rem;
	border: 3px solid var(--ql-border);
	border-top-color: var(--ql-accent);
	border-radius: 50%;
	animation: spin 0.8s linear infinite;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

.error-state {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 0.75rem;
	padding: 2rem;
	text-align: center;
	color: var(--ql-text-muted);
	word-break: break-word;
	overflow-wrap: anywhere;
}

.error-icon {
	width: 2.5rem;
	height: 2.5rem;
	color: var(--ql-danger, #ef4444);
	flex-shrink: 0;
}

.retry-btn {
	padding: 0.5rem 1rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: white;
	background: var(--ql-accent);
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
}

.retry-btn:hover {
	opacity: 0.9;
}
</style>
