// Coming back from FAC Cloud's checkout page.
//
// Payments are taken on FAC Cloud's own site, which returns the customer here
// with `?fac_checkout=<session>&result=<how it ended>`. The plan this app shows
// is cached, so without this the customer landed back on the plan they had
// just paid to leave. Run once for the whole app: the customer returns to
// whichever page they started the purchase from, not only the billing page.

import { getCurrentScope, onScopeDispose, ref } from "vue";

import { api } from "@/api/client";
import { useToast } from "@/composables/useToast";
import { logger } from "@/utils/logger";
import {
	announceBillingChange,
	onBillingChange,
	requestBillingReload,
} from "./_billing/billingRefresh";

const RESULTS = ["success", "processing", "cancelled", "failed"];
// `?success=true|false` and Stripe's `?checkout=success|cancelled`, from
// before the checkout page named its session.
const LEGACY_RESULTS = {
	true: "success",
	false: "cancelled",
	success: "success",
	cancelled: "cancelled",
};
// Everything a checkout return adds to the URL. `session_id` is left alone
// when a seat purchase returned: that handler reads it itself.
const MARKERS = ["fac_checkout", "result", "success", "checkout", "credit_purchase"];

const MESSAGES = {
	applied: "Payment confirmed — your account is up to date.",
	processing: "Payment received — your plan will update shortly.",
	cancelled: "Checkout cancelled. No changes were made.",
	failed: "The payment didn't go through. No changes were made to your plan.",
};

function first(value) {
	return Array.isArray(value) ? value[0] : value;
}

/**
 * What the URL says about a checkout the customer just came back from.
 *
 * @param {object} query  The route's query.
 * @returns {{session: string|null, result: string} | null}  null when this
 *          page load is not a checkout return.
 */
export function parseCheckoutReturn(query = {}) {
	const session = first(query.fac_checkout) || null;
	if (session) {
		const result = first(query.result);
		return { session, result: RESULTS.includes(result) ? result : "success" };
	}
	const legacy = LEGACY_RESULTS[first(query.success) ?? first(query.checkout)];
	return legacy ? { session: null, result: legacy } : null;
}

function withoutMarkers(query) {
	const kept = { ...query };
	MARKERS.forEach((key) => delete kept[key]);
	if (!("seat_purchase" in kept)) delete kept.session_id;
	return kept;
}

/**
 * @param {object} deps
 * @param {object} deps.router        vue-router instance.
 * @param {object} deps.userStore     Needs `isAdmin` and `loadQuota()`.
 * @param {number} [deps.pollIntervalMs]
 * @param {number} [deps.timeoutMs]   How long to wait for the purchase to land.
 */
export function useCheckoutReturn({
	router,
	userStore,
	pollIntervalMs = 2000,
	timeoutMs = 30000,
}) {
	const toast = useToast();
	// idle | confirming | applied | processing | unknown | cancelled | failed
	const state = ref("idle");
	let disposed = false;
	let sleeping = null;

	const unsubscribe = onBillingChange(() => {
		userStore.loadQuota();
		requestBillingReload();
	});

	function dispose() {
		disposed = true;
		unsubscribe();
		if (sleeping) {
			clearTimeout(sleeping.timer);
			sleeping.resolve();
		}
	}
	if (getCurrentScope()) onScopeDispose(dispose);

	function sleep(ms) {
		return new Promise((resolve) => {
			sleeping = { resolve, timer: setTimeout(resolve, ms) };
		});
	}

	async function poll(session) {
		const attempts = Math.floor(timeoutMs / pollIntervalMs) + 1;
		for (let attempt = 0; attempt < attempts && !disposed; attempt++) {
			if (attempt) await sleep(pollIntervalMs);
			if (disposed) break;
			try {
				const res = await api.billing.verifyCheckoutReturn(session);
				if (res?.done) return res.outcome || "unknown";
			} catch (err) {
				// A failed poll is not a failed payment; ask again.
				logger.warn("Checkout status check failed:", err);
			}
		}
		return "processing";
	}

	async function refresh() {
		await userStore.loadQuota();
		requestBillingReload();
		announceBillingChange();
	}

	function report(outcome) {
		if (outcome === "applied") toast.showSuccess(MESSAGES.applied);
		else if (outcome === "failed") toast.showError(MESSAGES.failed);
		else if (outcome === "cancelled") toast.showToast(MESSAGES.cancelled, "info", 5000);
		else toast.showToast(MESSAGES.processing, "info", 6000);
	}

	async function outcomeOf({ session, result }) {
		if (result === "cancelled" || result === "failed") return result;
		// Verifying needs billing access; everyone else just gets fresh numbers.
		if (!session || !userStore.isAdmin) return "unknown";

		state.value = "confirming";
		const pending = toast.showToast("Confirming your payment…", "info", 0);
		try {
			return await poll(session);
		} finally {
			toast.dismiss(pending);
		}
	}

	/** Handle this page load's checkout return, if it is one. */
	async function run() {
		await router.isReady();
		const parsed = parseCheckoutReturn(router.currentRoute.value.query);
		if (!parsed) return;

		const outcome = await outcomeOf(parsed);
		if (disposed) return;
		state.value = outcome;

		if (outcome !== "cancelled" && outcome !== "failed") await refresh();
		// Stripped last, from wherever the app is by now, so a reload while
		// polling asks again instead of forgetting the purchase.
		const current = router.currentRoute.value;
		await router.replace({ query: withoutMarkers(current.query), hash: current.hash });
		report(outcome);
	}

	return { state, run, dispose };
}
