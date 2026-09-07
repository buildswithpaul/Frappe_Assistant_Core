export function typeClass(type) {
	const known = ["info", "success", "warning", "feature", "promotion", "outage", "maintenance"];
	return `ntype-${known.includes(type) ? type : "info"}`;
}

// single source of truth for "outage-class" — pinned first in the center,
// surfaced in the assertive outage banner, excluded from the high-priority
// banner. Store and components both consume this rather than each keeping
// their own copy.
export const OUTAGE_TYPES = new Set(["outage", "maintenance"]);

// http(s)/mailto/same-site absolute paths only — target=_blank does not
// neutralize javascript: in every browser (ported from the old banner, FACO-M8).
export function safeActionUrl(raw) {
	if (!raw || typeof raw !== "string") return "";
	const trimmed = raw.trim();
	if (trimmed.startsWith("/") && !trimmed.startsWith("//")) return trimmed;
	if (/^mailto:/i.test(trimmed)) return trimmed;
	try {
		const u = new URL(trimmed);
		if (u.protocol === "http:" || u.protocol === "https:") return u.toString();
	} catch {
		/* fall through */
	}
	return "";
}
