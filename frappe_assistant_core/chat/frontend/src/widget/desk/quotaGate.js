import { QUOTA_KEY, cycleStart } from "@/components/spotlight/spotlightRules";

/**
 * Should this turn be refused before it is sent? Gates on the server's `credits_exhausted`
 * (AR's own admission rule: monthly quota spent AND no prepaid balance). The old
 * `percentage_used >= 100` counted the plan quota alone and refused exactly the tenants who
 * bought prepaid credits to keep working. An absent answer never blocks: a stale bundle
 * meeting a newer server is routine, and "the server didn't say" is not "the server said no".
 */
export function isBlocked(status) {
	if (!status || status.is_unlimited) return false;
	return status.credits_exhausted === true;
}

// Same key the old widget wrote, so a notice already dismissed this cycle stays dismissed.
const overageKey = (status, user) => QUOTA_KEY(user, cycleStart(status), "overage");

/** Admin-only: quota spent, prepaid credits covering it. A working state, announced once per cycle. */
export function overageNoticeDue(status, user, storage = localStorage) {
	if (!status || !status.is_admin) return false;
	if (!(status.in_overage && !status.credits_exhausted)) return false;
	return !storage.getItem(overageKey(status, user));
}

export function markOverageNoticeShown(status, user, storage = localStorage) {
	storage.setItem(overageKey(status, user), "1");
}
