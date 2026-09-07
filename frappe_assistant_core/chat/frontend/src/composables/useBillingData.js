import { ref, computed } from "vue";
import { useUserStore } from "@/stores/userStore";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";
import { formatDate } from "@/composables/useFormatters";

import { startHostedCheckout } from "./_billing/hostedCheckout";
import {
	formatCurrency,
	formatInvoiceDate,
	formatStatus,
	getPlanPriceMeta as _getPlanPriceMeta,
	getPlanPrice as _getPlanPrice,
	getPlanActionText as _getPlanActionText,
} from "./_billing/billingFormatters";

export function useBillingData() {
	const userStore = useUserStore();
	const isAdmin = computed(() => userStore.isAdmin);
	const quota = computed(() => userStore.quotaInfo);

	// Loading / error states
	const loading = ref(true);
	const error = ref(null);

	// Verification banner (for checkout return)
	const verificationMessage = ref(null);
	const verificationSuccess = ref(false);
	const invoiceInfo = ref(null);

	// Admin data
	const dashboardData = ref(null);
	const availablePlans = ref([]);
	const invoices = ref([]);
	const upcomingInvoice = ref(null);
	const billingCycle = ref("monthly");

	// Action states
	const upgrading = ref(false);
	const cancelling = ref(false);

	// Gateway selection modal state
	const showGatewayModal = ref(false);
	const availableGateways = ref([]);
	const selectedPlanForUpgrade = ref(null);
	const loadingGateways = ref(false);
	const gatewayError = ref(null);
	const reactivating = ref(false);
	const recommendedGateway = ref(null);
	const isFirstTimeCheckout = ref(true);

	// Downgrade confirmation modal state
	const showDowngradeConfirm = ref(false);
	// Cancel-subscription confirmation — same ConfirmModal pattern as
	// UsersSettings (no native browser confirm()).
	const showCancelConfirm = ref(false);

	// Billing details gate — GSTIN / country / state / address live on the
	// ERPNext Customer + Address. We require them *before* the checkout
	// modal opens so the first Sales Invoice is tagged correctly.
	const billingDetails = ref(null);
	const billingDetailsLoaded = ref(false);
	const pendingPlanAfterDetails = ref(null);
	// Plan the user clicked Upgrade on, currently parked behind the
	// ConfirmSubscriptionModal — `null` when the modal is closed. Holding
	// the plan here (rather than reusing selectedPlanForUpgrade) keeps the
	// confirm step independent of the gateway-picker state.
	const pendingConfirmPlan = ref(null);
	const billingDetailsGateMessage = ref("");

	// Scheduled change info
	const scheduledChange = ref(null);
	// Mirror of get_subscription_status().subscription so computeds can
	// read fresh fields (needs_mandate_reauth, payment_status, etc.) without
	// crawling the dashboard's nested usage payload.
	const subscriptionStatus = ref(null);
	const billingHistory = ref([]);
	const portalUrl = ref(null);

	// Prepaid credits
	const creditBalance = ref(null);
	const creditTransactions = ref([]);
	const showCreditPurchase = ref(false);
	const purchasingCredits = ref(false);

	// Promo code
	const showPromoInput = ref(false);
	const promoCode = ref("");
	const appliedPromo = ref(null);
	const promoError = ref(null);
	const validatingPromo = ref(false);

	// Computed
	// Prefer `subscription_status` for live money-state (cancel flag,
	// period end, payment_status). The dashboard `subscription` object
	// used to be quota-cache-only, so a cancelled-at-period-end plan
	// looked identical to an active one after refresh.
	const subscription = computed(() => {
		const dash = dashboardData.value?.subscription || {};
		const billing =
			dashboardData.value?.billing || dashboardData.value?.usage?.billing || {};
		const status = subscriptionStatus.value || {};
		return {
			...dash,
			plan: status.plan || dash.plan,
			status: status.status || dash.status,
			payment_status: status.payment_status || billing.payment_status || dash.payment_status,
			payment_gateway: status.payment_gateway || billing.payment_gateway || dash.payment_gateway,
			currency: billing.currency || dash.currency,
			billing_cycle: status.billing_cycle || dash.billing_cycle,
			cancel_at_period_end: !!(
				status.cancel_at_period_end ??
				billing.cancel_at_period_end ??
				dash.cancel_at_period_end
			),
			current_period_end:
				status.billing_cycle_end ||
				billing.current_period_end ||
				dash.current_period_end ||
				null,
			billing_cycle_start:
				status.billing_cycle_start ||
				billing.billing_cycle_start ||
				dash.billing_cycle_start ||
				null,
			referral: dash.referral || null,
		};
	});
	const currentPlan = computed(() => subscription.value?.plan || quota.value?.plan || "Free");
	const cancelAtPeriodEnd = computed(() => !!subscription.value?.cancel_at_period_end);
	/** Cancel→Free (or bare cancel flag). Paid scheduled downgrades also
	 * raise cancel_at_period_end on some gateways — those must still allow
	 * "Keep This Plan" on the current card. */
	const planChangesLocked = computed(() => {
		if (!cancelAtPeriodEnd.value) return false;
		const scheduled = (scheduledChange.value?.new_plan || "").toLowerCase();
		return !scheduled || scheduled === "free";
	});
	const periodEndDate = computed(() => {
		const raw = subscription.value?.current_period_end;
		if (!raw) return null;
		return formatDate(raw);
	});
	const referral = computed(() => subscription.value?.referral || null);

	const paymentFailed = computed(() => subscription.value?.payment_status === "past_due");
	const graceDaysRemaining = computed(() => {
		if (!paymentFailed.value) return 0;
		const periodEnd = subscription.value?.current_period_end;
		if (!periodEnd) return 0;
		const deadline = new Date(periodEnd);
		return Math.max(0, Math.ceil((deadline - new Date()) / 86400000));
	});

	// Set by AR (`charge_scheduler.charge_one`) when a renewal would
	// exceed the saved Razorpay mandate's per-debit cap (UPI Autopay's
	// ₹1,00,000 NPCI ceiling), or by `on_mandate_cancelled` when the
	// bank revokes the saved token. Reads off the subscription_status
	// payload — NOT the usage dashboard's billing block.
	const needsMandateReauth = computed(() => !!subscriptionStatus.value?.needs_mandate_reauth);
	const reauthorizing = ref(false);

	const hasScheduledChange = computed(() => !!scheduledChange.value?.new_plan);

	const billingDetailsComplete = computed(() => {
		const d = billingDetails.value;
		if (!d) return false;
		if (!d.billing_email || !d.billing_country) return false;
		// India Compliance splits CGST/SGST vs IGST off the billing state, so
		// we can't issue a valid Sales Invoice without it.
		if (d.billing_country === "IN" && !d.billing_state) return false;
		return true;
	});

	const scheduledChangeMessage = computed(() => {
		if (!hasScheduledChange.value) return "";
		const plan = scheduledChange.value.new_plan;
		const date = formatDate(scheduledChange.value.effective_date);
		return `Your plan will change to ${plan} on ${date}`;
	});

	const creditsPercentage = computed(() => {
		if (!quota.value || quota.value.is_unlimited) return 0;
		return Math.min(100, quota.value.percentage_used || 0);
	});

	const usageBarColor = computed(() => {
		const pct = creditsPercentage.value;
		if (pct >= 100) return "#ef4444";
		if (pct >= 90) return "#f97316";
		if (pct >= 80) return "#eab308";
		return "var(--ql-accent)";
	});

	const usageResetDate = computed(() => {
		const resetDate =
			dashboardData.value?.usage?.reset_date ||
			dashboardData.value?.usage?.next_billing_date ||
			subscription.value?.reset_date;
		if (!resetDate) return null;
		return formatDate(resetDate);
	});

	// Bound helpers — wrap the pure formatters with the composable's reactive
	// `billingCycle` so call-sites don't need to thread it through.
	function getPlanPriceMeta(plan) {
		return _getPlanPriceMeta(plan, billingCycle.value);
	}
	function getPlanPrice(plan) {
		return _getPlanPrice(plan, billingCycle.value);
	}
	function getPlanActionText(plan) {
		return _getPlanActionText(plan, {
			upgrading: upgrading.value,
			hasScheduledChange: hasScheduledChange.value,
			scheduledChange: scheduledChange.value,
			currentPlan: currentPlan.value,
			cancelAtPeriodEnd: planChangesLocked.value,
		});
	}

	async function loadBillingDetails() {
		try {
			const result = await api.billing.getBillingDetails();
			billingDetails.value = result || null;
		} catch (err) {
			// First-time users have no ERPNext Customer yet — backend returns
			// an empty result, so we treat missing as "not set", not an error.
			logger.warn("Failed to load billing details:", err);
			billingDetails.value = null;
		} finally {
			billingDetailsLoaded.value = true;
		}
	}

	// Data loading
	async function loadData() {
		loading.value = true;
		error.value = null;

		try {
			// Fire quota, checkout check, billing page data, and billing details
			// all in parallel. Billing details is needed synchronously by
			// handleUpgrade so we must have it loaded before the user can click.
			const [, , pageData] = await Promise.all([
				userStore.loadQuota(),
				checkForCheckoutReturn(),
				userStore.isAdmin
					? api.billing.getPageData({
							usage_history_days: 30,
							invoice_limit: 10,
							billing_history_limit: 20,
					  })
					: Promise.resolve(null),
				loadBillingDetails(),
			]);

			if (userStore.isAdmin && pageData) {
				const dashboard = pageData.dashboard;
				const plans = pageData.plans;
				const subStatus = pageData.subscription_status;

				dashboardData.value = dashboard;
				subscriptionStatus.value = subStatus?.subscription || null;
				scheduledChange.value = subStatus?.subscription?.scheduled_change || null;

				availablePlans.value = dashboard?.error
					? []
					: dashboard?.usage?.available_plans || plans?.plans || [];
				recommendedGateway.value = plans?.recommended_gateway || null;
				isFirstTimeCheckout.value = !dashboard?.usage?.billing?.has_payment_method;
				invoices.value = pageData.invoices?.invoices || [];
				upcomingInvoice.value = pageData.invoices?.upcoming_invoice || null;

				billingHistory.value = pageData.billing_history?.history || [];
				portalUrl.value = pageData.billing_history?.portal_url || null;

				const creditData = pageData.credit_balance;
				if (creditData && !creditData.error) {
					creditBalance.value = creditData.balance || 0;
					creditTransactions.value = creditData.transactions || [];
				} else {
					creditBalance.value = dashboard?.credit_balance ?? null;
					creditTransactions.value = [];
				}

				if (dashboard?.error) {
					error.value = dashboard.error;
				}
			}
		} catch (err) {
			error.value = err.message || "Failed to load billing information";
			logger.error("Failed to load billing data:", err);
		} finally {
			loading.value = false;
		}
	}

	async function refreshAllData() {
		await loadData();
	}

	// Credit purchase handling
	async function openCreditPurchase() {
		// Always refresh gateways so pack currency matches current billing
		// country — a stale cache from an earlier session could still carry
		// USD pack rates after India billing details were saved.
		try {
			const result = await api.billing.getAvailableGateways();
			if (result?.gateways?.length) {
				availableGateways.value = result.gateways;
			}
		} catch (err) {
			logger.error("Failed to load gateways:", err);
		}
		showCreditPurchase.value = true;
	}

	async function handleCreditPurchase({ creditAmount, gateway }) {
		purchasingCredits.value = true;
		try {
			showCreditPurchase.value = false;
			await startHostedCheckout("Credits", {
				credit_amount: creditAmount,
				gateway,
			});
		} catch (err) {
			verificationMessage.value = err.message || "Failed to initiate credit purchase";
			verificationSuccess.value = false;
		} finally {
			purchasingCredits.value = false;
		}
	}

	// Checkout return handling
	async function checkForCheckoutReturn() {
		const urlParams = new URLSearchParams(window.location.search);
		if (!urlParams.has("success")) {
			// Fast path: no checkout return parameters
			localStorage.removeItem("faco_checkout_session");
			return;
		}

		const success = urlParams.get("success");
		const sessionId =
			urlParams.get("session_id") || localStorage.getItem("faco_checkout_session");

		if (success === "true" && sessionId) {
			try {
				const result = await api.billing.verifyPayment(sessionId);
				if (result?.success) {
					verificationMessage.value =
						result.message || "Payment successful! Your plan has been upgraded.";
					verificationSuccess.value = true;
					invoiceInfo.value = result.invoice || null;
				} else {
					verificationMessage.value =
						result?.error || "Payment verification failed. Please contact support.";
					verificationSuccess.value = false;
				}
			} catch (err) {
				verificationMessage.value = "Failed to verify payment: " + err.message;
				verificationSuccess.value = false;
			}
		} else if (success === "false") {
			verificationMessage.value = "Payment was cancelled.";
			verificationSuccess.value = false;
		}

		localStorage.removeItem("faco_checkout_session");

		if (urlParams.has("success") || urlParams.has("session_id")) {
			window.history.replaceState({}, "", window.location.pathname);
		}
	}

	// Action handlers
	async function handleUpgrade(plan) {
		const planId = (plan.id || plan.name || "").toLowerCase();

		// Cancellation-at-period-end: plan CTAs are disabled in the picker,
		// but still guard here so a stale click / API caller cannot open
		// checkout. Keep my plan (reactivate) is the only undo path.
		if (planChangesLocked.value) {
			verificationMessage.value =
				"Your subscription is scheduled to cancel. Click Keep my plan first if you want to stay or change plans.";
			verificationSuccess.value = false;
			return;
		}

		if (hasScheduledChange.value && planId === currentPlan.value.toLowerCase()) {
			await handleCancelScheduledChange();
			return;
		}

		if (hasScheduledChange.value && planId === scheduledChange.value.new_plan.toLowerCase()) {
			return;
		}

		if (planId === currentPlan.value.toLowerCase()) return;

		if (planId === "enterprise") {
			window.open("mailto:sales@frappe.io?subject=FACO Enterprise Inquiry", "_blank");
			return;
		}

		if (planId === "free") {
			showDowngradeConfirm.value = true;
			return;
		}

		// Gate: billing details (country + state for India) must be saved
		// before we open the checkout modal, so the ERPNext Customer + Address
		// exists with the right GST category when the invoice is issued.
		if (!billingDetailsLoaded.value) {
			await loadBillingDetails();
		}
		if (!billingDetailsComplete.value) {
			pendingPlanAfterDetails.value = plan;
			const label = plan.display_name || plan.name || planId;
			billingDetailsGateMessage.value = `Please complete your billing details before subscribing to ${label}.`;
			return;
		}

		// Park the plan behind the ConfirmSubscriptionModal so the user
		// sees the mandate disclosure (eMandate / card-on-file) before the
		// Razorpay widget opens. `confirmAndCheckout` resumes the original
		// post-gate flow once they click Authorize.
		pendingConfirmPlan.value = plan;
	}

	function cancelConfirmSubscription() {
		pendingConfirmPlan.value = null;
	}

	async function confirmAndCheckout(payload) {
		// Backwards-tolerant: callers may pass `plan` directly OR
		// `{ plan, paymentMethod }` from the confirm modal.
		const plan = payload && payload.plan ? payload.plan : payload;
		const paymentMethod = payload && payload.paymentMethod ? payload.paymentMethod : null;

		pendingConfirmPlan.value = null;
		selectedPlanForUpgrade.value = plan;
		loadingGateways.value = true;
		gatewayError.value = null;

		let gateways = [];
		try {
			const result = await api.billing.getAvailableGateways();
			if (!result?.gateways?.length) {
				throw new Error(result?.error || "No payment gateways are enabled");
			}
			gateways = result.gateways;
		} catch (err) {
			logger.error("Error loading gateways:", err);
			availableGateways.value = [];
			gatewayError.value = err.message || "Failed to load payment options";
			// Surface the error inside the modal so the user sees it.
			showGatewayModal.value = true;
			loadingGateways.value = false;
			return;
		} finally {
			loadingGateways.value = false;
		}

		// Fast path: when only one gateway is enabled (today: Razorpay; Stripe
		// activates once we're approved — 6 months out), skip the picker and
		// go straight to checkout. The modal reappears automatically when
		// a second gateway is flipped on in AR Payment Gateway Settings.
		if (gateways.length === 1) {
			availableGateways.value = gateways;
			await proceedWithGateway({
				gateway: gateways[0].name,
				billingName: billingDetails.value?.billing_email?.split("@")[0] || null,
				billingEmail: billingDetails.value?.billing_email || null,
				paymentMethod,
			});
			selectedPlanForUpgrade.value = null;
			availableGateways.value = [];
			return;
		}

		availableGateways.value = gateways;
		showGatewayModal.value = true;
	}

	function closeGatewayModal() {
		showGatewayModal.value = false;
		selectedPlanForUpgrade.value = null;
		availableGateways.value = [];
		gatewayError.value = null;
	}

	async function proceedWithGateway(selection) {
		const gateway = selection.gateway;
		const billingName = selection.billingName || null;
		const billingEmail = selection.billingEmail || null;
		const paymentMethod = selection.paymentMethod || null;
		const planId = selectedPlanForUpgrade.value?.id || selectedPlanForUpgrade.value?.name;

		upgrading.value = true;
		try {
			// The plan change itself — including a downgrade, which is
			// scheduled rather than charged — is decided on FAC Cloud when
			// the checkout page opens. A change that costs nothing says so
			// there and comes straight back.
			await startHostedCheckout("Subscription", {
				plan: planId,
				billing_cycle: billingCycle.value,
				gateway,
				billing_name: billingName,
				billing_email: billingEmail,
				promo_code: appliedPromo.value?.code || null,
				payment_method: paymentMethod,
			});
		} catch (err) {
			logger.error("Checkout error:", err);
			if (err.message !== "Payment cancelled") {
				verificationMessage.value = "Failed to initiate checkout: " + (err.message || err);
				verificationSuccess.value = false;
			}
			closeGatewayModal();
			// Pull fresh state so the cards revert to the real plan if the
			// user abandoned checkout after the backend parked a `pending_plan`.
			// Without this, the "MOST POPULAR" card would keep showing
			// "Processing…" indefinitely and the current-plan pill would drift.
			try {
				await loadData();
			} catch (refreshErr) {
				logger.warn("Failed to refresh billing state after checkout error:", refreshErr);
			}
		} finally {
			upgrading.value = false;
		}
	}

	async function validatePromo(codeArg) {
		const code = (codeArg || promoCode.value || "").trim().toUpperCase();
		if (!code) {
			promoError.value = "Please enter a promo code";
			return;
		}

		validatingPromo.value = true;
		promoError.value = null;

		try {
			const plan =
				selectedPlanForUpgrade.value?.id || selectedPlanForUpgrade.value?.name || null;
			const result = await api.billing.validatePromoCode(code, plan);
			if (result?.valid) {
				appliedPromo.value = { ...result, code };
				promoError.value = null;
			} else {
				promoError.value = result?.error || "Invalid promo code";
				appliedPromo.value = null;
			}
		} catch (err) {
			logger.error("Promo validation error:", err);
			promoError.value = "Unable to validate promo code";
			appliedPromo.value = null;
		} finally {
			validatingPromo.value = false;
		}
	}

	function removePromo() {
		appliedPromo.value = null;
		promoCode.value = "";
		promoError.value = null;
		showPromoInput.value = false;
	}

	function requestCancel() {
		showCancelConfirm.value = true;
	}

	function dismissCancelConfirm() {
		if (cancelling.value) return;
		showCancelConfirm.value = false;
	}

	async function handleCancel() {
		cancelling.value = true;
		try {
			const result = await api.billing.cancelSubscription(false);
			if (result?.success) {
				const until = result.effective_date
					? formatDate(result.effective_date)
					: periodEndDate.value;
				verificationMessage.value = until
					? `Subscription cancelled. You keep full access until ${until}, then move to the Free plan.`
					: "Subscription cancelled. You keep full access until the end of your billing period, then move to the Free plan.";
				verificationSuccess.value = true;
				showCancelConfirm.value = false;
				await refreshAllData();
			} else {
				throw new Error(result?.error || "Failed to cancel subscription");
			}
		} catch (err) {
			logger.error("Cancel error:", err);
			verificationMessage.value = "Failed to cancel: " + (err.message || err);
			verificationSuccess.value = false;
		} finally {
			cancelling.value = false;
		}
	}

	async function handleReactivate() {
		reactivating.value = true;
		try {
			const result = await api.billing.reactivateSubscription();
			if (result?.success) {
				verificationMessage.value =
					result.message || "Subscription reactivated successfully!";
				verificationSuccess.value = true;
				await refreshAllData();
			} else {
				throw new Error(result?.error || "Failed to reactivate subscription");
			}
		} catch (err) {
			logger.error("Reactivate error:", err);
			verificationMessage.value = "Failed to reactivate: " + (err.message || err);
			verificationSuccess.value = false;
		} finally {
			reactivating.value = false;
		}
	}

	// Re-authorize the saved Razorpay mandate without changing plans.
	// Routed through the dedicated `reauthorize_mandate` endpoint (NOT
	// `initiateUpgrade` — which rejects "upgrade to the plan you're
	// already on" with "You are already on this plan"). The backend reads
	// the current plan + cycle off the subscription itself. The webhook
	// (`token.confirmed` → `confirm_token_on_mandate`) clears
	// `needs_mandate_reauth` once the new authorization completes.
	async function handleReauthorizeMandate() {
		if (reauthorizing.value) return;
		reauthorizing.value = true;
		try {
			const billingName = billingDetails.value?.billing_email?.split("@")[0] || null;
			await startHostedCheckout("Reauthorization", {
				billing_name: billingName,
			});
		} catch (err) {
			logger.error("Re-auth error:", err);
			if (err.message !== "Payment cancelled") {
				verificationMessage.value =
					"Failed to start re-authorization: " + (err.message || err);
				verificationSuccess.value = false;
			}
			await loadData();
		} finally {
			reauthorizing.value = false;
		}
	}

	async function confirmDowngradeToFree() {
		upgrading.value = true;
		try {
			const result = await api.billing.downgradeToFree();
			if (result.success) {
				verificationMessage.value =
					result.message ||
					"Your plan will be downgraded to Free at the end of your billing period.";
				verificationSuccess.value = true;
				await loadData();
			} else {
				throw new Error(result.error || "Failed to initiate downgrade");
			}
		} catch (err) {
			logger.error("Downgrade error:", err);
			verificationMessage.value = "Failed to downgrade: " + (err.message || err);
			verificationSuccess.value = false;
		} finally {
			upgrading.value = false;
			showDowngradeConfirm.value = false;
		}
	}

	async function handleCancelScheduledChange() {
		cancelling.value = true;
		try {
			const result = await api.billing.cancelScheduledChange();
			if (result.success) {
				verificationMessage.value =
					result.message ||
					"Scheduled plan change cancelled. You will continue on your current plan.";
				verificationSuccess.value = true;
				scheduledChange.value = null;
				await loadData();
			} else {
				throw new Error(
					result.error || result.message || "Failed to cancel scheduled change"
				);
			}
		} catch (err) {
			logger.error("Cancel scheduled change error:", err);
			verificationMessage.value =
				"Failed to cancel scheduled change: " + (err.message || err);
			verificationSuccess.value = false;
		} finally {
			cancelling.value = false;
		}
	}

	function dismissVerification() {
		verificationMessage.value = null;
		invoiceInfo.value = null;
	}

	/** Called by BillingSettings when BillingDetailsForm emits `saved`.
	 * Country changes reprice the whole page (INR ↔ USD), so we reload
	 * plans/quota/gateways — not just the details form. Without that the
	 * hero and Plans tab kept showing the old currency until a full
	 * browser refresh. */
	async function handleBillingDetailsSaved() {
		await loadBillingDetails();
		billingDetailsGateMessage.value = "";
		// Drop cached gateway pack rates so Buy Credits picks up the new
		// currency on the next open (openCreditPurchase also refreshes).
		availableGateways.value = [];
		await refreshAllData();
		if (pendingPlanAfterDetails.value && billingDetailsComplete.value) {
			const plan = pendingPlanAfterDetails.value;
			pendingPlanAfterDetails.value = null;
			await handleUpgrade(plan);
		} else {
			pendingPlanAfterDetails.value = null;
		}
	}

	function clearBillingDetailsGate() {
		pendingPlanAfterDetails.value = null;
		billingDetailsGateMessage.value = "";
	}

	return {
		// State
		loading,
		error,
		verificationMessage,
		verificationSuccess,
		invoiceInfo,
		dashboardData,
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
		isFirstTimeCheckout,
		showDowngradeConfirm,
		showCancelConfirm,
		scheduledChange,
		showCreditPurchase,
		purchasingCredits,
		creditBalance,
		creditTransactions,
		showPromoInput,
		promoCode,
		appliedPromo,
		promoError,
		validatingPromo,
		billingDetails,
		billingDetailsLoaded,
		billingDetailsGateMessage,
		pendingPlanAfterDetails,
		pendingConfirmPlan,

		// Computed
		isAdmin,
		billingDetailsComplete,
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
		refreshAllData,
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
		loadBillingDetails,
		handleBillingDetailsSaved,
		clearBillingDetailsGate,
	};
}
