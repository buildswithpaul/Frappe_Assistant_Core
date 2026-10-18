import { __ } from "@/utils/i18n";

// Time-aware greeting + a friendly display name derived from the username.
export function greetingForHour(hour) {
	const h = Number.isFinite(hour) ? hour : 12;
	if (h < 5) return "Good evening";
	if (h < 12) return "Good morning";
	if (h < 17) return "Good afternoon";
	return "Good evening";
}

// The whole headline per time of day, so each sentence is translatable as one.
export function greetingLineForHour(hour, name) {
	const greeting = greetingForHour(hour);
	if (greeting === "Good morning") return __("Good morning, {0}.", [name]);
	if (greeting === "Good afternoon") return __("Good afternoon, {0}.", [name]);
	return __("Good evening, {0}.", [name]);
}

export function displayNameFromUser(user) {
	if (!user || user === "Guest") return __("there");
	const local = String(user).split("@")[0];
	const first = local.split(/[._-]/)[0] || local;
	return first.charAt(0).toUpperCase() + first.slice(1);
}

// The user's Frappe language when the page has one, else the browser's. An invalid tag falls back too.
export function uiLocale() {
	const lang =
		(typeof window !== "undefined" && window.frappe?.boot?.lang) ||
		(typeof document !== "undefined" && document.documentElement?.lang) ||
		undefined;
	try {
		return lang ? Intl.getCanonicalLocales(lang)[0] : undefined;
	} catch {
		return undefined;
	}
}

// "Monday · 6 July" — the day and month order follows the locale.
export function formatDateLabel(date = new Date(), locale = uiLocale()) {
	const weekday = date.toLocaleDateString(locale, { weekday: "long" });
	const dayMonth = date.toLocaleDateString(locale, { day: "numeric", month: "long" });
	return `${weekday} · ${dayMonth}`;
}

// Compact relative time for Resume rows. Frappe datetimes are naive strings.
export function relativeTimeLabel(value, now = new Date(), locale = uiLocale()) {
	const then = value instanceof Date ? value : new Date(String(value).replace(" ", "T"));
	const diffMs = now - then;
	const mins = Math.floor(diffMs / 60000);
	if (mins < 1) return __("just now");
	if (mins < 60) return __("{0}m ago", [mins]);
	const hours = Math.floor(mins / 60);
	if (hours < 24 && then.getDate() === now.getDate()) return __("{0}h ago", [hours]);
	const days = Math.floor(diffMs / 86400000);
	if (days <= 1) return __("yesterday");
	if (days < 7) return __("{0}d ago", [days]);
	return then.toLocaleDateString(locale, { day: "numeric", month: "short" });
}
