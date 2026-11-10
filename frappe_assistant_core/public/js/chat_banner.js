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

// The 30-second demo (a YouTube video; see chat/demo_video.py). Played in a Desk dialog so the
// admin stays on the page, with a plain link for anyone whose network blocks the embed.
frappe_assistant_core.chat.show_demo_video = function () {
	const video = frappe.boot && frappe.boot.fac_demo_video;
	if (!video) return;
	const esc = frappe.utils.escape_html;
	const dialog = new frappe.ui.Dialog({
		title: __("FAC Chat in 30 seconds"),
		size: "large",
		fields: [{ fieldtype: "HTML", fieldname: "video" }],
	});
	dialog.fields_dict.video.$wrapper.html(`
		<div style="position: relative; aspect-ratio: 16 / 9; background: #000; border-radius: 8px; overflow: hidden;">
			<iframe src="${esc(video.embed)}" title="${esc(__("FAC Chat demo"))}"
				style="position: absolute; inset: 0; width: 100%; height: 100%; border: 0;"
				allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen></iframe>
		</div>
		<p class="text-muted small" style="margin-top: 8px;">
			<a href="${esc(video.url)}" target="_blank" rel="noopener noreferrer">${__("Open on YouTube")}</a>
		</p>`);
	// Stop playback when the dialog closes.
	dialog.onhide = () => dialog.fields_dict.video.$wrapper.empty();
	dialog.show();
};

frappe_assistant_core.chat._render_banner = function () {
	const has_video = !!(frappe.boot && frappe.boot.fac_demo_video);
	const demo_button = has_video
		? `<button type="button" class="btn btn-primary btn-xs fac-chat-banner-demo">${__("Watch the demo")}</button>`
		: "";
	const banner_html = `
		<div class="fac-chat-banner alert alert-info" style="margin: 10px 20px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
			<div style="flex: 1; min-width: 220px;">
				<strong>${__("FAC Chat is installed")}</strong> —
				${__("ask questions about your ERPNext data in plain words.")}
				${has_video ? __("Watch a 30-second demo, then switch it on in 2 minutes.") : __("Switch it on in 2 minutes.")}
			</div>
			${demo_button}
			<a href="/app/fac-admin" class="btn ${has_video ? "btn-default" : "btn-primary"} btn-xs">${__("Switch it on")}</a>
			<button type="button" class="btn btn-default btn-xs fac-chat-banner-dismiss">${__("Dismiss")}</button>
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

	$banner.find(".fac-chat-banner-demo").on("click", frappe_assistant_core.chat.show_demo_video);

	// The bell keeps the link after the banner is dismissed or scrolled away (once per admin).
	frappe.call({ method: "frappe_assistant_core.chat.api.banner_shown", type: "POST" });

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
