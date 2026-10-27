import { formatResetDate, nextResetDate } from "@/components/spotlight/spotlightRules";
import { percentUsed } from "@/utils/creditPercent";
import { personalLimitBlock } from "@/utils/personalLimit";

/**
 * This month's allowance as the billing cycle reports it, ready for AllowanceCard.
 * A fallback snapshot (the figures could not be loaded) reports a total of -1, so it is
 * flagged `unknown` rather than being read as an unlimited plan.
 */
export function monthAllowance(quota) {
	const unknown = Boolean(quota.is_fallback);
	const reset = unknown ? null : nextResetDate(quota);
	return {
		used: quota.quota_used,
		total: quota.quota_total,
		percent: percentUsed(quota),
		unlimited: !unknown && Boolean(quota.is_unlimited || quota.quota_total === -1),
		unknown,
		resetDate: reset ? formatResetDate(reset) : null,
	};
}

/** Members who have used their whole personal monthly limit (rows from users.list). */
export function countMembersAtLimit(users) {
	return (users || []).filter((u) => personalLimitBlock(u)).length;
}

/**
 * What the band shows for "members at their limit" from one page of members. AR caps a page at
 * 100, so a page with more behind it only gives a lower bound: "3+", or nothing to show at all.
 */
export function membersAtLimitLabel(result) {
	const count = countMembersAtLimit(result?.users);
	if (!result?.pagination?.has_more) return count;
	return count > 0 ? `${count}+` : null;
}

/** Whole credits in the browser locale, the same way the rest of the Usage page prints numbers. */
export function formatCredits(value) {
	return Math.round(Number(value) || 0).toLocaleString();
}
