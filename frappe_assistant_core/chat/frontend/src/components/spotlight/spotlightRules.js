/**
 * Which Spotlight to show, and what it says. Pure: no Vue, no network.
 * The Desk widget mirrors these rules in public/chat/widget/widget_spotlight.js;
 * widgetSpotlight.spec.js asserts the two agree. Change both or neither.
 */

export const DAILY_KEY = (user) => `fac_spotlight_last_shown:${user}`;
export const QUOTA_KEY = (user, cycle, threshold) => `fac_quota_moment:${user}:${cycle}:${threshold}`;
export const PLANS_ROUTE = "/settings/billing?tab=plans";
export const CREDITS_ROUTE = "/settings/billing?tab=credits";

const pad = (n) => String(n).padStart(2, "0");

export function localDate(now = new Date()) {
	return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

export function cycleStart(status, now = new Date()) {
	const raw = status?.billing_cycle_start;
	if (raw) return String(raw).slice(0, 10);
	return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-01`;
}

export function nextResetDate(status) {
	const raw = status?.billing_cycle_start;
	if (!raw) return null;
	const [y, m, d] = String(raw).slice(0, 10).split("-").map(Number);
	const last = new Date(y, m + 1, 0).getDate();
	return localDate(new Date(y, m, Math.min(d, last)));
}

export function quotaThreshold(status) {
	if (!status || status.is_unlimited || status.is_fallback) return 0;
	if (status.credits_exhausted === true) return 100;
	if (!status.in_overage && Number(status.percentage_used) >= 80) return 80;
	return 0;
}

export function pickAnnouncement(notifications) {
	return (notifications || []).find((n) => n.display_style === "modal" && !n.dismissed) || null;
}

const fmt = (n) => Math.max(0, Math.round(Number(n) || 0)).toLocaleString();

export function quotaContent(status) {
	const threshold = quotaThreshold(status);
	const hasUpgradeKey = Object.prototype.hasOwnProperty.call(status || {}, "upgrade");
	const upgrade = hasUpgradeKey ? status.upgrade : undefined;
	const reset = nextResetDate(status);
	const resetLine = reset ? ` Credits reset on ${reset}.` : "";

	const title = threshold === 100
		? "You've used all of this month's credits"
		: `You've used ${threshold}% of this month's credits`;
	const body = threshold === 100
		? `FAC Chat is paused for your workspace.${resetLine} Upgrade or buy credits to keep going now.`
		: `${fmt(status?.quota_remaining)} credits left on ${status?.plan || "your plan"}.${resetLine}`;

	const topPlan = hasUpgradeKey && upgrade === null;
	return {
		kind: "quota",
		id: `quota-${threshold}`,
		threshold,
		eyebrow: upgrade?.plan ? `With ${upgrade.plan} you get` : "Credits",
		title,
		body,
		highlights: Array.isArray(upgrade?.benefits) ? [...upgrade.benefits] : [],
		media: { art: "quota" },
		primary: topPlan
			? { label: "Buy credits", route: CREDITS_ROUTE }
			: { label: "See plans", route: PLANS_ROUTE },
		secondary: topPlan ? null : { label: "Buy credits", route: CREDITS_ROUTE },
	};
}

export function announcementContent(n) {
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
		} catch {
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
		media: n.media_url ? { url: n.media_url, type: n.media_type || "image", alt: n.media_alt || "" } : null,
		primary,
		secondary: { label: "Not now" },
	};
}

export const storage = {
	get(key) {
		try {
			return window.localStorage.getItem(key);
		} catch {
			return null;
		}
	},
	set(key, value) {
		try {
			window.localStorage.setItem(key, value);
		} catch {
			// Storage disabled: the cap and once-per-cycle rules hold for this page load only.
		}
	},
};
