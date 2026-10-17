// Pure helpers for the home "Needs you" section.

export const TONE_RANK = { danger: 0, warning: 1, neutral: 2 };

const UNKNOWN_TONE_RANK = Object.keys(TONE_RANK).length;

function toneRank(item) {
	return TONE_RANK[item.tone] ?? UNKNOWN_TONE_RANK;
}

/**
 * Merge the server-ranked signals with the client-only attention item.
 * Sorted by tone (stable, so server order holds within a tone); the attention
 * item leads the dangers; then capped.
 */
export function mergeSignals(serverItems, attentionItem, cap) {
	const items = attentionItem ? [attentionItem, ...(serverItems || [])] : [...(serverItems || [])];
	// Array.prototype.sort is stable, and the attention item is already first.
	items.sort((a, b) => toneRank(a) - toneRank(b));
	return items.slice(0, cap);
}
