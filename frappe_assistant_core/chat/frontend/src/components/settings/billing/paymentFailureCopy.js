const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// AR sends naive server dates ("2026-10-06", "2026-10-05 00:02:47"). Parsing
// them with Date would shift the day for viewers west of UTC, so read the
// calendar parts directly.
export function shortDate(value) {
	const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value || "");
	if (!match) return "";
	const month = MONTHS[Number(match[2]) - 1];
	return month ? `${Number(match[3])} ${month}` : "";
}

/** The sentences FAC shows for AR's `payment_failure` block, or null. */
export function paymentFailureLines(failure) {
	if (!failure) return null;
	const pastDue = !!failure.past_due;
	const retry =
		!pastDue && failure.next_retry_on
			? `We'll try again on ${shortDate(failure.next_retry_on)} (attempt ${
					(failure.attempt || 0) + 1
			  } of ${failure.total_attempts}).`
			: "";
	return {
		headline: `Your payment on ${shortDate(failure.failed_at)} didn't go through.`,
		reason: failure.reason || "",
		retry,
		pastDue,
	};
}
