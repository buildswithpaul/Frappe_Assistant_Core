/**
 * A random (version 4) UUID. crypto.randomUUID exists only in a secure context
 * (https or localhost), so on a site served over plain http no message could be
 * sent; getRandomValues works in any context.
 */
export function randomUUID() {
	const bytes = crypto.getRandomValues(new Uint8Array(16));
	bytes[6] = (bytes[6] & 0x0f) | 0x40; // version 4
	bytes[8] = (bytes[8] & 0x3f) | 0x80; // RFC 4122 variant
	const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
	return [hex.slice(0, 8), hex.slice(8, 12), hex.slice(12, 16), hex.slice(16, 20), hex.slice(20)].join("-");
}
