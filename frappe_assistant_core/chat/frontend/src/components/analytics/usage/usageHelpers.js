import { formatResetDate, nextResetDate } from "@/components/spotlight/spotlightRules";
import { personalLimitBlock } from "@/utils/personalLimit";

/** This month's allowance as the billing cycle reports it, ready for AllowanceCard. */
export function monthAllowance(quota) {
	const reset = nextResetDate(quota);
	return {
		used: quota.quota_used,
		total: quota.quota_total,
		percent: Math.min(100, Math.round(Number(quota.percentage_used) || 0)),
		unlimited: Boolean(quota.is_unlimited || quota.quota_total === -1),
		resetDate: reset ? formatResetDate(reset) : null,
	};
}

/** Members who have used their whole personal monthly limit (rows from users.list). */
export function countMembersAtLimit(users) {
	return (users || []).filter((u) => personalLimitBlock(u)).length;
}
