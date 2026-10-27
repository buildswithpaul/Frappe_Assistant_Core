/**
 * The one rule for "how much of the allowance is used", so the Usage band, the billing ring,
 * the chat meter and the Spotlight title never disagree: round down, and show 100 only when
 * the allowance is really spent (99.6% reads 99, not "exhausted").
 */

/** Whole percent of `total` that `used` represents; 0 when there is no allowance to measure. */
export function percentOf(used, total) {
	const u = Number(used);
	const t = Number(total);
	if (!(t > 0) || !Number.isFinite(u)) return 0;
	if (u >= t) return 100;
	return Math.min(99, Math.max(0, Math.floor((u / t) * 100)));
}

/** Same rule for a quota snapshot; `percentage_used` is the fallback when used/total are missing. */
export function percentUsed(quota) {
	const hasFigures = quota && quota.quota_used != null && quota.quota_total != null;
	if (hasFigures) return percentOf(quota.quota_used, quota.quota_total);
	const reported = Number(quota?.percentage_used) || 0;
	return reported >= 100 ? 100 : Math.min(99, Math.max(0, Math.floor(reported)));
}
