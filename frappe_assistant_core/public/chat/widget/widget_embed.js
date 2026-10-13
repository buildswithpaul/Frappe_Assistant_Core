// Frappe Assistant Core - widget loader for standalone Frappe apps
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
// chat/embed/inject.py adds this to the pages of apps an admin enabled
// (Helpdesk, Insights, CRM…). They have no frappe.boot, so the built entry
// comes from get_widget_entry. Any failure leaves the page as it was.
(function () {
	"use strict";
	if (window.frappe && window.frappe.boot) return; // Desk loads the widget itself.
	fetch("/api/method/frappe_assistant_core.chat.api.settings.embed.get_widget_entry", {
		credentials: "same-origin",
		headers: { Accept: "application/json" },
	})
		.then(function (r) {
			return r.ok ? r.json() : null;
		})
		.then(function (data) {
			var cfg = data && data.message;
			if (!cfg || !cfg.entry) return;
			return import(cfg.entry).then(function (m) {
				return m.bootEmbedded(cfg);
			});
		})
		.catch(function (err) {
			console.warn("[FAC widget] failed to start", err);
		});
})();
