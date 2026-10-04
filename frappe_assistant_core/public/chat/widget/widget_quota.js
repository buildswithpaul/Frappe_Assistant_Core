// Frappe Assistant Copilot - Powered by FAC Cloud - Widget Quota Module
// Handles quota status. Quota moments render inside the panel via
// FACOWidgetSpotlight; nothing pops over Desk.

/**
 * Widget Quota Module
 * Responsible for quota status and deciding which quota moment is due.
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

			const moment = this.check_quota_warnings(widget, data);
			if (moment && moment.kind === "overage") {
				// Decided at Desk load, usually with the panel closed: the notice
				// is shown (and the once-per-cycle key written) on the next open.
				widget.overage_notice_due = true;
				if (widget.is_open) {
					this.show_pending_overage_notice(widget);
				}
			}
			window.FACOWidgetSpotlight.update_dot(widget);

			return data;
		} catch (error) {
			FACOLogger.error("Error fetching quota status:", error);
			return null;
		}
	},

	/**
	 * Render the overage notice if one is due, and only then mark it shown
	 * for this billing cycle, so a notice decided while the panel was closed
	 * is not spent unseen.
	 * @param {Object} widget - Widget instance
	 */
	show_pending_overage_notice(widget) {
		const data = widget.quota_status;
		if (!widget.overage_notice_due || !data) {
			return;
		}
		const S = window.FACOWidgetSpotlight;
		widget.overage_notice_due = false;
		S.render_notice(
			widget,
			__(
				"Your monthly credits are used up — FAC Chat is now drawing on your prepaid credits ({0} left).",
				[this.format_credits(data.credit_balance)],
			),
		);
		S.storage_set(this.overage_key(widget, data), "1");
	},

	overage_key(widget, data) {
		const S = window.FACOWidgetSpotlight;
		const user = widget.user || (window.frappe && window.frappe.session && window.frappe.session.user) || "";
		return `fac_quota_moment:${user}:${S.cycle_start(data)}:overage`;
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
	 * Decide which quota moment, if any, is due. Opens nothing: the caller
	 * renders it inside the panel (FACOWidgetSpotlight) and the launcher dot.
	 *
	 * Admin-only. Non-admins can't act on a quota moment (the upgrade and
	 * purchase flows are admin-gated); if their request later fails because
	 * the tenant is at 100%, the streaming layer surfaces the API error inline.
	 *
	 * The overage switchover is marked shown by show_pending_overage_notice
	 * when it renders, so it is announced once per billing cycle. The 80/100
	 * moments are marked when dismissed.
	 * @param {Object} widget - Widget instance
	 * @param {Object} data - Payload from get_quota_status
	 * @returns {Object|null} {kind: "overage"}, a quota_content object, or null
	 */
	check_quota_warnings(widget, data) {
		if (!data || !data.is_admin) {
			return null;
		}
		const S = window.FACOWidgetSpotlight;
		const user = widget.user || (window.frappe && window.frappe.session && window.frappe.session.user) || "";
		const cycle = S.cycle_start(data);

		// Quota spent, prepaid credits covering the difference: a working
		// state, not a failure. Mark the switchover once, then stay quiet.
		if (data.in_overage && !data.credits_exhausted) {
			return S.storage_get(this.overage_key(widget, data)) ? null : { kind: "overage" };
		}

		const threshold = S.quota_threshold(data);
		if (!threshold || S.storage_get(S.quota_key(user, cycle, threshold))) {
			return null;
		}
		return S.quota_content(data);
	},
};
