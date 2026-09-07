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

			const percentage = data.percentage_used || 0;

			// Check for warning thresholds
			this.check_quota_warnings(widget, percentage, data.is_admin);

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
	 * Check and show quota warning modals at thresholds
	 * @param {Object} widget - Widget instance
	 * @param {number} percentage - Percentage used
	 * @param {boolean} is_admin - Whether user is admin
	 */
	check_quota_warnings(widget, percentage, is_admin) {
		// Quota modals are admin-only. Non-admins can't act on them
		// (the upgrade and purchase flows are admin-gated), so surfacing
		// "you're at 80%" to them creates anxiety without agency. If a
		// non-admin's request later fails because the tenant is at 100%,
		// the streaming layer surfaces the API error inline — that's
		// the right place for them to learn about it.
		if (!is_admin) {
			return;
		}

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

		// 100% - Hard block
		if (percentage >= 100 && !shown["100"]) {
			shown["100"] = true;
			save();
			this.show_quota_blocked_modal(widget, is_admin);
		}
		// 90% warning
		else if (percentage >= 90 && percentage < 100 && !shown["90"]) {
			shown["90"] = true;
			save();
			this.show_quota_warning_modal(widget, 90, is_admin);
		}
		// 80% warning
		else if (percentage >= 80 && percentage < 90 && !shown["80"]) {
			shown["80"] = true;
			save();
			this.show_quota_warning_modal(widget, 80, is_admin);
		}
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
	 * Show hard block modal when quota is 100% exhausted.
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
