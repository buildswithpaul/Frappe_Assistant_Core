import {
	DAILY_KEY,
	QUOTA_KEY,
	cycleStart,
	localDate,
	pickAnnouncement,
	quotaThreshold,
	storage,
} from "@/components/spotlight/spotlightRules";

const SURFACE = "widget";

async function call(method) {
	try {
		const r = await window.frappe.call({ method, type: "GET", args: {} });
		return r && r.message;
	} catch {
		return null;
	}
}

// The launcher shows a dot only for users who could act on it, as the old widget did:
// seated, registered, and past privacy consent.
async function isFullySetUp(access) {
	if (!access.can_use) return false;
	if (!(access.preferences && access.preferences.privacy_consent_complete)) return false;
	const auth = await call("frappe_assistant_core.chat.api.auth.get_user_auth_status");
	return !!(auth && auth.success && auth.ready);
}

/** Same decision as the panel's spotlight card: a due quota moment, else an unseen announcement today. */
export async function refreshSpotlightDot(view, access) {
	if (!(await isFullySetUp(access))) return view.setDot(false);

	const user = (window.frappe && window.frappe.session && window.frappe.session.user) || "";

	const quota = await call("frappe_assistant_core.chat.api.billing.quota.get_quota_status");
	if (quota && quota.success && quota.is_admin) {
		const threshold = quotaThreshold(quota);
		if (threshold && !storage.get(QUOTA_KEY(user, cycleStart(quota), threshold))) {
			return view.setDot(true);
		}
	}

	const notifications = await call("frappe_assistant_core.chat.api.notifications.get_notifications");
	const announcement = pickAnnouncement(notifications && notifications.notifications);
	const shownToday = storage.get(DAILY_KEY(user, SURFACE)) === localDate();
	view.setDot(!!announcement && !shownToday);
}
