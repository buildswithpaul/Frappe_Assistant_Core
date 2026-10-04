// Frappe Assistant Core - Widget Spotlight
// Mirrors chat/frontend/src/components/spotlight/spotlightRules.js - the
// widgetSpotlight.spec.js parity test fails if the two disagree.
// Never pops over Desk: a dot on the launcher, a card inside the open panel.

(function () {
	const PLANS_ROUTE = "/settings/billing?tab=plans";
	const CREDITS_ROUTE = "/settings/billing?tab=credits";
	const NOTIF_GET = "frappe_assistant_core.chat.api.notifications.get_notifications";
	const NOTIF_DISMISS = "frappe_assistant_core.chat.api.notifications.dismiss_notification";
	const HTML_ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

	const pad = (n) => String(n).padStart(2, "0");
	const fmt = (n) => Math.max(0, Math.round(Number(n) || 0)).toLocaleString();
	const esc = (s) =>
		window.frappe && window.frappe.utils && window.frappe.utils.escape_html
			? window.frappe.utils.escape_html(String(s ?? ""))
			: String(s ?? "").replace(/[&<>"']/g, (c) => HTML_ESCAPES[c]);

	window.FACOWidgetSpotlight = {
		daily_key: (user) => `fac_spotlight_last_shown:${user}`,
		quota_key: (user, cycle, threshold) => `fac_quota_moment:${user}:${cycle}:${threshold}`,

		local_date(now = new Date()) {
			return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
		},

		cycle_start(status, now = new Date()) {
			const raw = status?.billing_cycle_start;
			if (raw) return String(raw).slice(0, 10);
			return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-01`;
		},

		next_reset_date(status) {
			const raw = status?.billing_cycle_start;
			if (!raw) return null;
			const [y, m, d] = String(raw).slice(0, 10).split("-").map(Number);
			const last = new Date(y, m + 1, 0).getDate();
			return this.local_date(new Date(y, m, Math.min(d, last)));
		},

		format_reset_date(iso) {
			const [y, m, d] = iso.split("-").map(Number);
			return new Date(y, m - 1, d).toLocaleDateString("en-US", {
				month: "short",
				day: "numeric",
				year: "numeric",
			});
		},

		quota_threshold(status) {
			if (!status || status.is_unlimited || status.is_fallback) return 0;
			if (status.credits_exhausted === true) return 100;
			if (!status.in_overage && Number(status.percentage_used) >= 80) return 80;
			return 0;
		},

		pick_announcement(notifications) {
			return (notifications || []).find((n) => n.display_style === "modal" && !n.dismissed) || null;
		},

		quota_content(status) {
			const threshold = this.quota_threshold(status);
			const has_upgrade_key = Object.prototype.hasOwnProperty.call(status || {}, "upgrade");
			const upgrade = has_upgrade_key ? status.upgrade : undefined;
			const reset = this.next_reset_date(status);
			const reset_line = reset ? ` Credits reset on ${this.format_reset_date(reset)}.` : "";

			const title =
				threshold === 100
					? "You've used all of this month's credits"
					: `You've used ${threshold}% of this month's credits`;
			const body =
				threshold === 100
					? `FAC Chat is paused for your workspace.${reset_line} Upgrade or buy credits to keep going now.`
					: `${fmt(status?.quota_remaining)} credits left on ${status?.plan || "your plan"}.${reset_line}`;

			const top_plan = has_upgrade_key && upgrade === null;
			return {
				kind: "quota",
				id: `quota-${threshold}`,
				threshold,
				eyebrow: upgrade?.plan ? `With ${upgrade.plan} you get` : "Credits",
				title,
				body,
				highlights: Array.isArray(upgrade?.benefits) ? [...upgrade.benefits] : [],
				media: { art: "quota" },
				primary: top_plan
					? { label: "Buy credits", route: CREDITS_ROUTE }
					: { label: "See plans", route: PLANS_ROUTE },
				secondary: top_plan ? null : { label: "Buy credits", route: CREDITS_ROUTE },
			};
		},

		announcement_content(n) {
			const label = n.action_label && String(n.action_label).trim() ? n.action_label : "Got it";
			const primary = { label };

			// Validate route: must start with / (not // or /\) and have no whitespace
			if (n.action_route && /^\/(?![/\\])/.test(n.action_route) && !/\s/.test(n.action_route)) {
				primary.route = n.action_route;
			} else if (n.action_url) {
				// Validate URL: must parse and have http/https protocol
				try {
					const url = new URL(n.action_url);
					if (url.protocol === "http:" || url.protocol === "https:") {
						primary.url = n.action_url;
					}
				} catch (e) {
					// Invalid URL or not a URL, skip
				}
			}

			return {
				kind: "announcement",
				id: n.id,
				eyebrow: n.eyebrow || "",
				title: n.title,
				body: n.message || "",
				highlights: Array.isArray(n.highlights) ? n.highlights : [],
				media: n.media_url
					? { url: n.media_url, type: n.media_type || "image", alt: n.media_alt || "" }
					: null,
				primary,
				secondary: { label: "Not now" },
			};
		},

		storage_get(key) {
			try {
				return window.localStorage.getItem(key);
			} catch (e) {
				return null;
			}
		},

		storage_set(key, value) {
			try {
				window.localStorage.setItem(key, value);
			} catch (e) {
				// Storage disabled: the cap and once-per-cycle rules hold for this page load only.
			}
		},

		// --- Widget actions ---

		_user(widget) {
			return widget.user || (window.frappe && window.frappe.session && window.frappe.session.user) || "";
		},

		_quota_moment(widget) {
			const status = widget.quota_status;
			if (!status || !status.is_admin) return null;
			const threshold = this.quota_threshold(status);
			if (!threshold) return null;
			if (this.storage_get(this.quota_key(this._user(widget), this.cycle_start(status), threshold))) {
				return null;
			}
			return this.quota_content(status);
		},

		pending(widget) {
			if (!(widget.can_use && widget.user_setup_complete && widget.privacy_consent_complete)) {
				return null;
			}
			const quota = this._quota_moment(widget);
			if (quota) return quota;
			const n = this.pick_announcement(widget.spotlight_notifications);
			if (n && this.storage_get(this.daily_key(this._user(widget))) !== this.local_date()) {
				return this.announcement_content(n);
			}
			return null;
		},

		async refresh(widget) {
			try {
				const r = await frappe.call({ method: NOTIF_GET, type: "GET", args: {} });
				widget.spotlight_notifications = (r && r.message && r.message.notifications) || [];
			} catch (e) {
				widget.spotlight_notifications = widget.spotlight_notifications || [];
			}
			this.update_dot(widget);
		},

		update_dot(widget) {
			const $btn = widget.$widget.find(".faco-toggle-btn");
			$btn.find(".faco-spotlight-dot").remove();
			if (this.pending(widget)) {
				$btn.append('<span class="faco-spotlight-dot" aria-hidden="true"></span>');
			}
		},

		_open(target) {
			if (!target) return;
			if (target.route) {
				window.open("/copilot" + target.route, "_blank", "noopener");
				return;
			}
			if (!target.url) return;
			try {
				const url = new URL(target.url);
				if (url.protocol === "http:" || url.protocol === "https:") {
					window.open(url.href, "_blank", "noopener");
				}
			} catch (e) {
				// Invalid URL: nothing to open.
			}
		},

		_dismiss(widget, content) {
			if (content.kind === "quota") {
				const key = this.quota_key(
					this._user(widget),
					this.cycle_start(widget.quota_status),
					content.threshold,
				);
				this.storage_set(key, "1");
			} else {
				Promise.resolve(
					frappe.call({ method: NOTIF_DISMISS, args: { notification_id: content.id } }),
				).catch(() => {});
				(widget.spotlight_notifications || []).forEach((n) => {
					if (n.id === content.id) n.dismissed = true;
				});
			}
			widget.$widget.find(".faco-spotlight-card").remove();
			this.update_dot(widget);
		},

		_media_html(media) {
			if (!media || !media.url) return "";
			const reduce =
				window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
			if (media.type === "video") {
				return `<video class="faco-spot-media" src="${esc(media.url)}" aria-label="${esc(media.alt)}" muted loop playsinline ${reduce ? "controls" : "autoplay"} onerror="this.remove()"></video>`;
			}
			return `<img class="faco-spot-media" src="${esc(media.url)}" alt="${esc(media.alt)}" onerror="this.remove()">`;
		},

		render_in_panel(widget, content = this.pending(widget)) {
			const $messages = widget.$widget.find(".faco-messages");
			$messages.find(".faco-spotlight-card").remove();
			if (!content) return;
			if (content.kind === "announcement") {
				this.storage_set(this.daily_key(this._user(widget)), this.local_date());
				this.update_dot(widget);
			}
			const highlights = (content.highlights || []).map((h) => `<li>${esc(h)}</li>`).join("");
			const html = `
				<div class="faco-spotlight-card" role="region" aria-label="${esc(content.title)}">
					<button class="faco-spot-close" data-spot="dismiss" aria-label="${esc(__("Dismiss"))}">&#10005;</button>
					${this._media_html(content.media)}
					${content.eyebrow ? `<div class="faco-spot-eyebrow">${esc(content.eyebrow)}</div>` : ""}
					<div class="faco-spot-title">${esc(content.title)}</div>
					${content.body ? `<div class="faco-spot-body">${esc(content.body)}</div>` : ""}
					${highlights ? `<ul class="faco-spot-highlights">${highlights}</ul>` : ""}
					<button class="faco-spot-primary" data-spot="primary">${esc(content.primary.label)}</button>
					${content.secondary ? `<button class="faco-spot-secondary" data-spot="secondary">${esc(content.secondary.label)}</button>` : ""}
				</div>`;
			$messages.prepend(html);
			const $card = $messages.find(".faco-spotlight-card");
			$card.find("[data-spot='primary']").on("click", () => {
				this._dismiss(widget, content);
				this._open(content.primary);
			});
			$card.find("[data-spot='secondary']").on("click", () => {
				this._dismiss(widget, content);
				this._open(content.secondary);
			});
			$card.find("[data-spot='dismiss']").on("click", () => this._dismiss(widget, content));
		},

		render_notice(widget, text) {
			const $messages = widget.$widget.find(".faco-messages");
			$messages.find(".faco-spotlight-notice").remove();
			$messages.prepend(`<div class="faco-spotlight-notice">${esc(text)}</div>`);
		},
	};
})();
