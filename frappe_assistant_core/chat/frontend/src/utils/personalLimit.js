/**
 * A member who has used their whole personal monthly limit: `{used, limit}`, or null.
 *
 * Prepaid credits belong to the team and never raise a personal limit, because AR checks the
 * limit first (user_limit_reached). A limit of 0 means none: the member draws on the team pool.
 */
export function personalLimitBlock(status) {
	if (!status || status.has_individual_limit === false) return null;
	const limit = Number(status.monthly_credit_limit) || 0;
	if (limit <= 0) return null;
	const used = Number(status.credits_used_this_month) || 0;
	return used >= limit ? { used, limit } : null;
}
