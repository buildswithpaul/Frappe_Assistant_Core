// Frappe Assistant Core - AI Assistant integration for Frappe Framework
// Copyright (C) 2025 Paul Clinton
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program.  If not, see <https://www.gnu.org/licenses/>.

frappe.ui.form.on("FAC Chat Settings", {
	refresh(frm) {
		if (frm.doc.registration_status !== "Registered") {
			frm.add_custom_button(
				__("Register in FAC Chat"),
				() => frm.trigger("start_registration"),
				__("Actions")
			);
		}

		// Nothing to clear on a site that was never registered.
		if (frm.doc.registration_status !== "Not Registered") {
			frm.add_custom_button(
				__("Reset Registration"),
				() => frm.trigger("reset_registration"),
				__("Actions")
			);
		}

		const indicators = {
			Registered: [__("Connected to FAC Cloud"), "green"],
			"Pending Email Verification": [__("Awaiting Email Verification"), "orange"],
			Waitlisted: [__("Waitlisted"), "blue"],
			Error: [__("Registration Error"), "red"],
		};
		const [label, colour] = indicators[frm.doc.registration_status] || [
			__("Not Registered"),
			"orange",
		];
		frm.dashboard.add_indicator(label, colour);
	},

	start_registration(frm) {
		/**
		 * Registration happens in the FAC Chat onboarding screen, not here.
		 *
		 * Registering means accepting a specific Terms and Conditions version,
		 * and AR rejects any registration whose terms_version it did not just
		 * publish. Terms can only be accepted where they are shown, so Desk
		 * hands off rather than posting a version it never displayed.
		 *
		 * `/copilot` is a website route, not a Desk page — set_route() would
		 * resolve it under /app and 404.
		 */
		window.open("/copilot", "_blank");
	},

	reset_registration(frm) {
		// Mirror of the resolved site_config value, refreshed on migrate. Shown
		// because re-registering against a different FAC Cloud mints a NEW
		// tenant — the old subscription, credits and history stay behind.
		const fac_cloud_url = frm.doc.fac_cloud_url || __("(not configured)");

		frappe.warn(
			__("Reset FAC Cloud registration?"),
			__(
				"This clears the tenant credentials this site signs its requests with. FAC Chat stops working until the site is registered again.<br><br>Re-registration goes to <b>{0}</b> and creates a <b>new tenant</b> there. Any subscription, credits and history belonging to the current tenant stay where they are and are not carried over.",
				[frappe.utils.escape_html(fac_cloud_url)]
			),
			() => {
				frappe.call({
					method: "frappe_assistant_core.chat.api.reset_registration",
					freeze: true,
					freeze_message: __("Clearing registration..."),
					callback: (r) => {
						if (r.message && r.message.success) {
							frappe.show_alert(
								{ message: r.message.message, indicator: "green" },
								7
							);
							frm.reload_doc();
						} else {
							frappe.msgprint({
								title: __("Reset Failed"),
								indicator: "red",
								message: r.message?.error || __("Unknown error occurred"),
							});
						}
					},
					error: () => {
						frappe.msgprint({
							title: __("Reset Failed"),
							indicator: "red",
							message: __("Could not reach the reset endpoint."),
						});
					},
				});
			},
			__("Reset Registration"),
			false
		);
	},
});
