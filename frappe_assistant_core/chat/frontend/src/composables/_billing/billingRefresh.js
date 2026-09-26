// How the rest of the app learns that billing state changed.
//
// Within this tab, `billingReloadTick` is bumped and the billing page reloads
// when it sees it move. Across tabs, a BroadcastChannel carries the same news:
// a customer who paid in one tab otherwise kept seeing the old plan in every
// other tab until they reloaded it themselves.

import { ref } from "vue";

const CHANNEL = "fac-billing";
const BILLING_UPDATED = "billing-updated";

export const billingReloadTick = ref(0);

export function requestBillingReload() {
	billingReloadTick.value += 1;
}

// One channel per tab for both sending and listening: a channel never
// receives its own messages, so the tab that announces does not also react
// to the announcement.
let channel;

function sharedChannel() {
	if (channel !== undefined) return channel;
	try {
		channel = typeof BroadcastChannel === "undefined" ? null : new BroadcastChannel(CHANNEL);
	} catch (_) {
		channel = null;
	}
	return channel;
}

export function announceBillingChange() {
	sharedChannel()?.postMessage({ type: BILLING_UPDATED });
}

/** Call `callback` when another tab announces a change. Returns an unsubscribe. */
export function onBillingChange(callback) {
	const ch = sharedChannel();
	if (!ch) return () => {};
	const handler = (event) => {
		if (event?.data?.type === BILLING_UPDATED) callback();
	};
	ch.addEventListener("message", handler);
	return () => ch.removeEventListener("message", handler);
}
