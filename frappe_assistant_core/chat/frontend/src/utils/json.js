/** JSON columns arrive as strings or as parsed values; a bad string yields the fallback. */
export function parseJsonMaybe(value, fallback) {
	if (value === null || value === undefined || value === "") return fallback;
	if (typeof value !== "string") return value;
	try {
		return JSON.parse(value);
	} catch {
		return fallback;
	}
}
