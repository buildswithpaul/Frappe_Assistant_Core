/**
 * Suggested replies (#35327): when a reply ends with a question or an offer to go on, FAC Cloud
 * sends a few short answers the user might give. The chat shows them as buttons under the latest
 * reply; a tap sends the answer as the user's own message. The relay stores the same block on the
 * reply, so a reload brings the buttons back.
 */

export const SUGGESTED_REPLIES_BLOCK = "suggested_replies";
export const MAX_SUGGESTED_REPLIES = 3;
const MAX_REPLY_CHARS = 80;

/** The answers from an event or a stored block that can be shown: short single-line strings. */
export function suggestedReplies(replies) {
	if (!Array.isArray(replies)) return [];
	const seen = new Set();
	const clean = [];
	for (const reply of replies) {
		if (typeof reply !== "string") continue;
		const text = reply.split(/\s+/).filter(Boolean).join(" ");
		if (!text || text.length > MAX_REPLY_CHARS || seen.has(text.toLowerCase())) continue;
		seen.add(text.toLowerCase());
		clean.push(text);
	}
	return clean.slice(0, MAX_SUGGESTED_REPLIES);
}

/** The answers to show under a reply: only the latest reply, only once it has finished. */
export function repliesToShow(message, { isLatest, isStreaming }) {
	if (!isLatest || isStreaming || !message || message.role !== "assistant") return [];
	const block = (message.blocks || []).find((b) => b.type === SUGGESTED_REPLIES_BLOCK);
	return suggestedReplies(block?.replies);
}
