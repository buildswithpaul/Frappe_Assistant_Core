// Payments leave this site.
//
// A payment gateway is onboarded against one declared website, and this app
// runs on a different domain for every customer — so the gateway widget can
// never legitimately open here. Every purchase now redirects to FAC Cloud's
// own checkout page and comes back afterwards, which is the same shape the
// Stripe branches already had.

import { api } from "@/api/client";

/**
 * The old allow-list of gateway hostnames does not apply here: the address
 * of the FAC Cloud checkout page is configured per deployment, so there is
 * no fixed host to compare against. What we can still insist on is that the
 * link our own backend handed us is one a browser will not downgrade —
 * https, or a loopback host while developing.
 */
export function assertHostedCheckoutUrl(url) {
	let parsed;
	try {
		parsed = new URL(url);
	} catch (_) {
		throw new Error("Invalid checkout URL");
	}
	const loopback = ["localhost", "127.0.0.1", "[::1]"].includes(parsed.hostname);
	if (parsed.protocol !== "https:" && !(parsed.protocol === "http:" && loopback)) {
		throw new Error("Checkout URL must use https");
	}
	return parsed.toString();
}

/**
 * Swap a purchase intent for a link, and follow it.
 *
 * Never resolves on success — the browser navigates away. Callers should
 * treat a return from this function as a failure to launch.
 *
 * @param {string} purpose  Subscription | Payment Method | Credits | Pack | Seat
 * @param {object} params   Purpose-specific arguments.
 * @param {string} returnTo Where FAC Cloud sends the user back to. Defaults
 *                          to the current page.
 */
export async function startHostedCheckout(purpose, params = {}, returnTo = null) {
	const result = await api.billing.createHostedCheckout(
		purpose,
		params,
		returnTo || window.location.href,
	);
	if (result?.error) throw new Error(result.error);
	if (!result?.checkout_url) throw new Error("Could not start checkout");

	window.location.href = assertHostedCheckoutUrl(result.checkout_url);
}
