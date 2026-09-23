// Pure helpers for the Members tab (unit-tested in __tests__/membersTab.spec.js).

const DAY_MS = 86400 * 1000;

/** True if the user hasn't been active in `days` days (null = never active = idle). */
export function isIdle(lastActivity, days = 30) {
	if (!lastActivity) return true;
	const ts = new Date(lastActivity).getTime();
	if (Number.isNaN(ts)) return true;
	return Date.now() - ts >= days * DAY_MS;
}

/**
 * Short expiry hint for a pending invite, computed from its `modified`
 * timestamp (the clock resets on resend). Invites lapse `days` (default 7)
 * after their last change.
 *
 * Returns one of: "expired" (past the window), "expires today" (last day),
 * "expires tomorrow", or "expires in N days". A missing/invalid timestamp
 * returns "" so callers can treat the absence as "no hint to show".
 */
export function inviteExpiry(modifiedTs, days = 7) {
	if (!modifiedTs) return "";
	const ts = new Date(modifiedTs).getTime();
	if (Number.isNaN(ts)) return "";

	const expiresAt = ts + days * DAY_MS;
	const msLeft = expiresAt - Date.now();
	if (msLeft <= 0) return "expired";

	const daysLeft = Math.ceil(msLeft / DAY_MS);
	if (daysLeft <= 1) return "expires today";
	if (daysLeft === 2) return "expires tomorrow";
	return `expires in ${daysLeft} days`;
}

/**
 * True when a pending invite is within `threshold` days of lapsing (or has
 * already lapsed) — drives the warning colour on the expiry hint. A
 * missing/invalid timestamp is treated as not-soon (no warning).
 */
export function inviteExpiringSoon(modifiedTs, days = 7, threshold = 2) {
	if (!modifiedTs) return false;
	const ts = new Date(modifiedTs).getTime();
	if (Number.isNaN(ts)) return false;
	const msLeft = ts + days * DAY_MS - Date.now();
	return msLeft <= threshold * DAY_MS;
}

/** True if adding one more user would require a prorated seat purchase.
 *
 *  A seat nobody is sitting in has already been paid for, so filling it is
 *  free — this is what stops an admin buying a second seat when the first
 *  one's invite never landed. `vacant_seats` is authoritative when AR sends
 *  it; without it we fall back to the seat minimum, which is what older AR
 *  builds can tell us.
 *
 *  Shared by useAddUserFlow (the charge decision) and InviteModal (the
 *  seat-impact notice) so the two can never disagree.
 */
export function seatChargeRequired(limit) {
	if (!limit) return false;
	const perUser = !!limit.is_per_user || (limit.price_per_user || 0) > 0;
	if (!perUser) return false;

	if (limit.vacant_seats != null) return limit.vacant_seats <= 0;

	const minUsers = limit.min_users || limit.max_users || 999;
	return (limit.active_users || 0) >= minUsers;
}

// Relative-time display ("2h ago", "3d ago") is provided by the shared
// formatRelativeTime in @/composables/useFormatters — don't duplicate it here.

// --- Member-management audit feed --------------------------------------------

/** Map a stored user_role value to its UI label (AR persists Member as "User"). */
function roleLabel(role) {
	if (role === "User") return "Member";
	return role || "Member";
}

/**
 * Safely parse the audit-log `details` field, which arrives as a JSON STRING
 * from the server (AR's frappe.as_json). Returns {} on null/invalid; tolerates
 * an already-parsed object so callers never have to second-guess the shape.
 */
export function parseAuditDetails(details) {
	if (!details) return {};
	if (typeof details === "object") return Array.isArray(details) ? {} : details;
	try {
		const parsed = JSON.parse(details);
		return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
	} catch {
		return {};
	}
}

/**
 * Human phrase for an audit entry: the action clause only (e.g. "invited
 * b@e.com as Member"). The caller renders the actor and timestamp separately
 * so it can bold the actor — this returns just the verb + target + any extra.
 */
export function describeAuditEntry(entry) {
	const target = entry.target_user_id || "a member";
	const d = parseAuditDetails(entry.details);
	switch (entry.action) {
		case "User Invited":
			return `invited ${target}${d.role ? ` as ${roleLabel(d.role)}` : ""}`;
		case "Invite Revoked":
			return `revoked the invite for ${target}`;
		case "Invite Resent":
			return `resent the invite to ${target}`;
		case "User Activated":
			return `joined the workspace`;
		case "User Role Changed":
			return `changed ${target}'s role to ${roleLabel(d.new_role)}`;
		case "User Credit Limit Changed":
			return `set ${target}'s credit limit to ${d.limit ?? "—"}`;
		case "User Suspended":
			return `suspended ${target}`;
		case "User Reactivated":
			return `reactivated ${target}`;
		case "User Removed":
			return `removed ${target}`;
		default:
			return `${entry.action} — ${target}`;
	}
}
