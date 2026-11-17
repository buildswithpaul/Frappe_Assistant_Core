// Codes that are expected states, not failures worth a support ticket.
// A denylist: turn failure codes are open-ended, the non-reportable ones are known.
const NOT_REPORTABLE = new Set([
	"low_balance",
	"quota_exhausted",
	"user_limit_reached",
	"INTERRUPT_ALREADY_RESOLVED",
]);

/** An unknown failure (no code) is reportable too. */
export function isReportable(code) {
	return !code || !NOT_REPORTABLE.has(code);
}

/** Seed text for the issue form; the session id is deliberately left out. */
export function buildReportPrefill({ code, message, at }) {
	return `Error: ${message || ""}\nCode: ${code || "unknown"}\nTime: ${at}\n\n`;
}
