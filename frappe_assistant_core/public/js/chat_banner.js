// Frappe Assistant Core - FAC Chat discovery banner
// Copyright (C) 2025 Paul Clinton
//
// This program is free software: you can redistribute it and/or modify it under
// the terms of the GNU Affero General Public License as published by the Free
// Software Foundation, either version 3 of the License, or (at your option) any
// later version. See https://www.gnu.org/licenses/.
//
// Loads on every Frappe Desk page. The server-side endpoint
// frappe_assistant_core.chat.api.should_show_banner enforces all eligibility
// rules: user must have write permission on Assistant Core Settings, FAC Chat
// must be currently disabled, and the user must not have previously dismissed
// the banner. Once dismissed, the banner never reappears for that user.

frappe.provide("frappe_assistant_core.chat");

frappe_assistant_core.chat._render_banner = function () {
	const banner_html = `
		<div class="fac-chat-banner alert alert-info" style="margin: 10px 20px; display: flex; align-items: center; gap: 12px;">
			<div style="flex: 1;">
				<strong>New in FAC 3.0: FAC Chat</strong> — an in-Frappe AI chat assistant.
			</div>
			<a href="/app/fac-admin" class="btn btn-primary btn-xs">Enable it</a>
			<button type="button" class="btn btn-default btn-xs fac-chat-banner-dismiss">Dismiss</button>
		</div>
	`;

	const $banner = $(banner_html);
	// Prepend to the main content region. Use the first matching selector
	// so the banner survives Desk style changes across Frappe versions.
	const $target = $(".main-section, .layout-main-section, .page-body").first();
	if (!$target.length) {
		// Desk DOM not yet ready or unsupported page type. Bail silently —
		// the banner will appear on the next page load that has a target.
		return;
	}
	$target.prepend($banner);

	$banner.find(".fac-chat-banner-dismiss").on("click", function () {
		frappe.call({
			method: "frappe_assistant_core.chat.api.dismiss_banner",
			type: "POST",
			callback: function () {
				$banner.fadeOut(150, function () {
					$(this).remove();
				});
			},
			error: function () {
				// Even if the server call fails, hide the banner client-side
				// so we don't badger the user. The dismissal will retry on next
				// page load.
				$banner.remove();
			},
		});
	});
};

frappe_assistant_core.chat._check_and_show_banner = function () {
	// Only run on Desk pages — skip portal/website routes where frappe.call
	// might not be available or the layout selectors are different.
	if (!window.frappe || !frappe.call || !frappe.session) {
		return;
	}
	if (frappe.session.user === "Guest") {
		return;
	}
	frappe.call({
		method: "frappe_assistant_core.chat.api.should_show_banner",
		type: "GET",
		callback: function (r) {
			if (r && r.message === true) {
				frappe_assistant_core.chat._render_banner();
			}
		},
	});
};

$(document).ready(function () {
	// Defer slightly so the Desk layout is in place before we try to inject.
	setTimeout(frappe_assistant_core.chat._check_and_show_banner, 500);
});
