// Frappe Assistant Core - Desk widget bootstrap
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
// app_include_js loads classic scripts, so this stays one: it reads the
// built entry from Desk boot info and imports it. No boot info means the
// frontend was not built on this site — no launcher, no error.
(function () {
	"use strict";
	function start() {
		var cfg = window.frappe && window.frappe.boot && window.frappe.boot.fac_widget;
		if (!cfg || !cfg.entry) return;
		import(cfg.entry)
			.then(function (m) {
				return m.boot(cfg);
			})
			.catch(function (err) {
				console.warn("[FAC widget] failed to start", err);
			});
	}
	if (document.readyState === "complete") start();
	else window.addEventListener("load", start, { once: true });
})();
