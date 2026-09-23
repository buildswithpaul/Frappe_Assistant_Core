export const CHAT_WIDTHS = { cozy: "720px", wide: "960px" };

export function resolveReadWidth(pref) {
	return CHAT_WIDTHS[pref] || CHAT_WIDTHS.wide;
}
