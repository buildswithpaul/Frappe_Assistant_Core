// Frappe Assistant Copilot - Powered by FAC Cloud - Widget Quota Module
// Handles quota display and warnings

/**
 * Widget Quota Module
 * Responsible for quota management and warning display.
 * Upgrade/billing flows are handled by the SPA at /copilot/ (Settings > Billing).
 */
window.FACOWidgetQuota = {
	/**
	 * Fetch current quota status
	 * @param {Object} widget - Widget instance
	 * @returns {Promise<Object>} Quota status
	 */
	async fetch_quota_status(widget) {
		try {
			const response = await frappe.call({
				method: "frappe_assistant_core.chat.api.billing.quota.get_quota_status",
				type: "GET",
				args: {},
			});

			const data = response.message;
			if (!data || !data.success) {
				return null;
			}

			// Store quota state for warning checks
			widget.quota_status = data;

			// Unlimited quota (dev mode) — no warnings needed
			if (data.is_unlimited) {
				return data;
			}

			// Check for warning thresholds
			this.check_quota_warnings(widget, data);

			return data;
		} catch (error) {
			FACOLogger.error("Error fetching quota status:", error);
			return null;
		}
	},

	/**
	 * Format credit numbers for user-facing display.
	 * Rounds to whole numbers below 1K (avoids the
	 * "60.874000000000024" raw-float bug); uses K/M
	 * suffixes with one decimal beyond that.
	 * @param {number} num - Number to format
	 * @returns {string} Formatted string
	 */
	format_credits(num) {
		const n = Number(num) || 0;
		if (n >= 1000000) {
			return (n / 1000000).toFixed(1) + "M";
		} else if (n >= 1000) {
			return (n / 1000).toFixed(1) + "K";
		}
		return Math.round(n).toString();
	},

	/**
	 * Should this turn be refused before it is even sent?
	 *
	 * Gates on the server's `credits_exhausted` — AR's own admission rule:
	 * the monthly quota is spent AND no prepaid balance is left. The old
	 * test, `percentage_used >= 100`, counted the plan quota alone, so it
	 * refused precisely the tenants who had bought prepaid credits in order
	 * to keep working. AR would have served them; the SPA did serve them;
	 * only the widget said no.
	 *
	 * An absent answer never blocks. Widget assets are cached for 12h, so a
	 * bundle and a server of different vintages meeting is routine, and
	 * "the server didn't say" is not "the server said no".
	 *
	 * @param {Object} quota_status - Payload from get_quota_status
	 * @returns {boolean} True only when every credit is genuinely gone
	 */
	is_blocked(quota_status) {
		if (!quota_status || quota_status.is_unlimited) {
			return false;
		}
		return quota_status.credits_exhausted === true;
	},

	/**
	 * Check and show quota modals at their thresholds.
	 * @param {Object} widget - Widget instance
	 * @param {Object} data - Payload from get_quota_status
	 */
	check_quota_warnings(widget, data) {
		// Quota modals are admin-only. Non-admins can't act on them
		// (the upgrade and purchase flows are admin-gated), so surfacing
		// "you're at 80%" to them creates anxiety without agency. If a
		// non-admin's request later fails because the tenant is at 100%,
		// the streaming layer surfaces the API error inline — that's
		// the right place for them to learn about it.
		const is_admin = !!(data && data.is_admin);
		if (!is_admin) {
			return;
		}

		const percentage = data.percentage_used || 0;

		// Use sessionStorage so warnings persist across page navigations within the same session
		// (clears when tab closes, so admins see warnings again in a new session)
		const storageKey = "faco_quota_warnings_shown";
		let shown = {};
		try {
			shown = JSON.parse(sessionStorage.getItem(storageKey) || "{}");
		} catch (e) {
			shown = {};
		}

		const save = () => sessionStorage.setItem(storageKey, JSON.stringify(shown));

		const once = (key, show) => {
			if (shown[key]) {
				return;
			}
			shown[key] = true;
			save();
			show();
		};

		// Every credit gone, quota and prepaid alike. The only blocking state.
		if (data.credits_exhausted) {
			once("100", () => this.show_quota_blocked_modal(widget, is_admin));
			return;
		}

		// Quota spent, prepaid credits covering the difference. This is a
		// working state, not a failure — the tenant bought credits for exactly
		// this. Mark the switchover once so it isn't silent (the credits are
		// finite and now draining), then stay out of the way.
		if (data.in_overage) {
			once("overage", () => this.show_quota_overage_notice(widget, is_admin));
			return;
		}

		// 90% / 80% warnings — the nudge to top up BEFORE the overage starts.
		// No upper bound: on the version skew above, percentage can read past
		// 100 with no verdict attached, and a warning is the honest reading.
		if (percentage >= 90) {
			once("90", () => this.show_quota_warning_modal(widget, 90, is_admin));
		} else if (percentage >= 80) {
			once("80", () => this.show_quota_warning_modal(widget, 80, is_admin));
		}
	},

	/**
	 * Tell an admin, once per session, that the monthly quota is spent and
	 * prepaid credits have taken over. Informational and dismissible — the
	 * turn goes through either way. Admin-only for the same reason the
	 * warnings are: a member cannot buy credits, so this would be anxiety
	 * without agency.
	 * @param {Object} widget - Widget instance
	 * @param {boolean} is_admin - Whether user is admin
	 */
	show_quota_overage_notice(widget, is_admin) {
		if (!is_admin) {
			return;
		}
		const balance = (widget.quota_status || {}).credit_balance || 0;

		const dialog = new frappe.ui.Dialog({
			title: __("Now using prepaid credits"),
			indicator: "blue",
			fields: [
				{
					fieldtype: "HTML",
					options: `
						<div class="faco-quota-overage-content">
							<div class="faco-quota-overage-icon">💳</div>
							<h4>${__("Your monthly quota is used up")}</h4>
							<p>${__("Requests now draw on your prepaid credits — {0} remaining.", [
								this.format_credits(balance),
							])}</p>
							<p style="margin-top: 12px; color: var(--text-muted);">
								${__("Your quota resets at the start of next month.")}
							</p>
						</div>
					`,
				},
			],
			primary_action_label: __("Got it"),
			primary_action: () => dialog.hide(),
			secondary_action_label: __("View Billing"),
			secondary_action: () => {
				dialog.hide();
				window.location.href = "/copilot/chat?tab=billing";
			},
		});

		dialog.show();
	},

	/**
	 * Show quota warning modal at 80% and 90% thresholds.
	 * Only invoked for admins — non-admins can't act on a warning
	 * (the upgrade flow is admin-gated), so they see nothing until
	 * the hard block at 100%. See `check_quota_warnings` for the gate.
	 * @param {Object} widget - Widget instance
	 * @param {number} threshold - Warning threshold
	 * @param {boolean} is_admin - Whether user is admin (always true here)
	 */
	show_quota_warning_modal(widget, threshold, is_admin) {
		if (!is_admin) {
			return;
		}
		const quota = widget.quota_status || {};
		const remaining = quota.quota_remaining || 0;

		const dialog = new frappe.ui.Dialog({
			title: threshold >= 90 ? __("Low Quota Warning") : __("Quota Notice"),
			indicator: threshold >= 90 ? "orange" : "yellow",
			fields: [
				{
					fieldtype: "HTML",
					options: `
						<div class="faco-quota-warning-content">
							<div class="faco-quota-warning-icon">
								${threshold >= 90 ? "⚠️" : "📊"}
							</div>
							<h4>${__("You've used {0}% of your monthly quota", [threshold])}</h4>
							<p>${__("Remaining credits: {0}", [this.format_credits(remaining)])}</p>
							<p style="margin-top: 12px; color: var(--text-muted);">
								${__("Upgrade your plan or purchase additional credits.")}
							</p>
						</div>
					`,
				},
			],
			primary_action_label: __("Upgrade Now"),
			primary_action: () => {
				dialog.hide();
				window.location.href = "/copilot/chat?tab=billing";
			},
			secondary_action_label: __("Maybe Later"),
			secondary_action: () => dialog.hide(),
		});

		dialog.show();
	},

	/**
	 * Show hard block modal when every credit is gone — monthly quota spent
	 * AND no prepaid balance left. Never fires while prepaid credits remain;
	 * see `is_blocked`.
	 * Admin-only: non-admins are intentionally not shown any quota
	 * modal. Defensive guard so a stray future caller can't bypass
	 * the policy. See `check_quota_warnings` for the rationale.
	 * @param {Object} widget - Widget instance
	 * @param {boolean} is_admin - Whether user is admin
	 */
	show_quota_blocked_modal(widget, is_admin) {
		if (!is_admin) {
			return;
		}
		const dialog = new frappe.ui.Dialog({
			title: __("Quota Exceeded"),
			indicator: "red",
			fields: [
				{
					fieldtype: "HTML",
					options: `
						<div class="faco-quota-blocked-content">
							<div class="faco-quota-blocked-icon">🚫</div>
							<h4>${__("You've reached your monthly quota limit")}</h4>
							<p>${__("Your quota will reset at the beginning of next month.")}</p>
							<p style="margin-top: 12px;">
								${__("Upgrade your plan or purchase credits to continue using FACO.")}
							</p>
						</div>
					`,
				},
			],
			primary_action_label: __("Upgrade Now"),
			primary_action: () => {
				dialog.hide();
				window.location.href = "/copilot/chat?tab=billing";
			},
		});

		// Remove close button to enforce action
		dialog.$wrapper.find(".modal-header .close").hide();
		dialog.show();
	},
};
