/**
 * Reads a tool_call block's `result` defensively.
 *
 * A result reaches the SPA in several shapes: the object a tool returned; a JSON string
 * (a persisted turn, or a truncated SSE payload); or the MCP content parts the runtime
 * streams and stores, `[{"text": "<json>"}]` (Strands) or `[{"type": "text", "text": "<json>"}]`
 * (the FAC MCP server), optionally inside a `{content, isError, structuredContent}` wrapper.
 * All of them unwrap to the tool's own object; anything that is not a parseable JSON object
 * counts as having no fields.
 */

const REASON_MAX = 140;

const isObject = (value) => Boolean(value) && typeof value === "object" && !Array.isArray(value);

function parseObject(text) {
	if (typeof text !== "string") return null;
	try {
		return unwrap(JSON.parse(text));
	} catch {
		return null;
	}
}

function fromParts(parts) {
	for (const part of parts) {
		if (!isObject(part)) continue;
		const found = isObject(part.json) ? part.json : parseObject(part.text);
		if (found) return found;
	}
	return null;
}

function unwrap(value) {
	if (Array.isArray(value)) return fromParts(value);
	if (!isObject(value)) return null;
	if (isObject(value.structuredContent)) return value.structuredContent;
	if (Array.isArray(value.content)) return fromParts(value.content) ?? value;
	return value;
}

export function toolResult(block) {
	const result = block?.result;
	return (typeof result === "string" ? parseObject(result) : unwrap(result)) ?? {};
}

// Only same-site paths and web URLs become links; anything else (javascript:) is a label.
export function safeUrl(value) {
	if (typeof value !== "string") return null;
	const url = value.trim();
	if (/^\/(?![\/\\])/.test(url) || /^https?:\/\//i.test(url)) return url;
	return null;
}

/** The form a successful customisation write changes: `{doctype, url}` with a safe url, or null. */
export function appliesTo(block) {
	if (toolFailed(block) || isDryRun(block)) return null;
	const target = toolResult(block).applies_to;
	const url = safeUrl(target?.url);
	return url && typeof target.doctype === "string" && target.doctype ? { doctype: target.doctype, url } : null;
}

export function toolFailed(block) {
	return block?.status === "error" || block?.result?.isError === true || toolResult(block).success === false;
}

/** A create that only ran validation: it saved nothing, so it must not read as a created record. */
export function isDryRun(block) {
	return block?.input?.validate_only === true || toolResult(block).validation_passed === true;
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
