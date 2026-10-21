/**
 * Reads a tool_call block's `result` defensively.
 *
 * The stream hands the SPA an object, but a result can also arrive as a string
 * (a persisted turn, or a truncated SSE payload), so anything that is not a
 * parseable JSON object counts as having no fields.
 */

const REASON_MAX = 140;

export function toolResult(block) {
	let result = block?.result;
	if (typeof result === "string") {
		try {
			result = JSON.parse(result);
		} catch {
			return {};
		}
	}
	return result && typeof result === "object" && !Array.isArray(result) ? result : {};
}

// Only same-site paths and web URLs become links; anything else (javascript:) is a label.
export function safeUrl(value) {
	if (typeof value !== "string") return null;
	const url = value.trim();
	if (/^\/(?![\/\\])/.test(url) || /^https?:\/\//i.test(url)) return url;
	return null;
}

export function toolFailed(block) {
	return block?.status === "error" || toolResult(block).success === false;
}

/** One short sentence saying why a step failed, or "" when there is nothing safe to show. */
export function failureReason(block, maxLength = REASON_MAX) {
	if (!toolFailed(block)) return "";
	const result = toolResult(block);
	const raw = [result.error, result.message].find((v) => typeof v === "string" && v.trim());
	if (!raw || /Traceback \(most recent call last\)/i.test(raw)) return "";
	const sentence = raw.trim().split(/\n|(?<=[.!?])\s/)[0].trim();
	return sentence.length > maxLength ? `${sentence.slice(0, maxLength - 1)}…` : sentence;
}
