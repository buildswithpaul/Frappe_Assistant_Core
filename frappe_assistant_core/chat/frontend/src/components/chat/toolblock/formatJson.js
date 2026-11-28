// Formatting deeply nested JSON grows it many times over; past this the text is shown as it came.
const MAX_FORMATTED_CHARS = 300000;

/**
 * JSON text re-indented without being parsed into values, so no number is rewritten on the way
 * (1.10 stays 1.10, a 20-digit id keeps its digits). Text that is not JSON, or that would grow
 * past the cap, comes back as it was.
 */
export function formatJson(text) {
	try {
		JSON.parse(text);
	} catch {
		return text;
	}
	let out = "";
	let depth = 0;
	let inString = false;
	const newline = () => `\n${"  ".repeat(depth)}`;
	for (let i = 0; i < text.length; i += 1) {
		const char = text[i];
		if (inString) {
			out += char;
			if (char === "\\") out += text[(i += 1)];
			else if (char === '"') inString = false;
		} else if (char === '"') {
			inString = true;
			out += char;
		} else if (char === "{" || char === "[") {
			const close = /^\s*[}\]]/.exec(text.slice(i + 1, i + 40));
			if (close) {
				out += char + close[0].trim();
				i += close[0].length;
			} else {
				depth += 1;
				out += char + newline();
			}
		} else if (char === "}" || char === "]") {
			depth -= 1;
			out += newline() + char;
		} else if (char === ",") out += char + newline();
		else if (char === ":") out += ": ";
		else if (!/\s/.test(char)) out += char;
		if (out.length > MAX_FORMATTED_CHARS) return text;
	}
	return out;
}
