// Keeps an open billing page from going stale.
//
// It reloads when a checkout return (in this tab or another) says the plan
// changed, and when the customer comes back to the tab — the usual way back
// from paying in another window. Tab switches are throttled: that reload hits
// FAC Cloud, and flicking between tabs should not.

import { onBeforeUnmount, onMounted, watch } from "vue";

import { billingReloadTick } from "./_billing/billingRefresh";

/**
 * @param {(options: {silent: boolean}) => unknown} reload  Reloads the page's
 *        data; `silent` asks it not to swap the page for a loading state.
 * @param {object} [options]
 * @param {number} [options.throttleMs]  Minimum gap between visibility reloads.
 */
export function useBillingAutoRefresh(reload, { throttleMs = 30000 } = {}) {
	let lastReload = Date.now();

	function refresh() {
		lastReload = Date.now();
		reload({ silent: true });
	}

	function onVisibilityChange() {
		if (document.visibilityState !== "visible") return;
		if (Date.now() - lastReload < throttleMs) return;
		refresh();
	}

	watch(billingReloadTick, refresh);
	onMounted(() => document.addEventListener("visibilitychange", onVisibilityChange));
	onBeforeUnmount(() => document.removeEventListener("visibilitychange", onVisibilityChange));
}
