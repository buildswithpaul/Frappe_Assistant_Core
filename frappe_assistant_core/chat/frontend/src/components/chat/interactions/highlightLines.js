/**
 * Highlighted code split into lines that each stand alone as HTML.
 *
 * highlight.js wraps a token in one <span>, and a token may run over several lines (a
 * triple-quoted string, a block comment). Cutting the HTML at every newline would leave such a
 * span open on one line and closed on a later one, so each line closes the spans still open at
 * its end and the next line opens them again.
 */
const TAG = /<span[^>]*>|<\/span>/g;

export function highlightedLines(html) {
	const open = [];
	return html.split("\n").map((line) => {
		const prefix = open.join("");
		for (const tag of line.match(TAG) || []) {
			if (tag === "</span>") open.pop();
			else open.push(tag);
		}
		return prefix + line + "</span>".repeat(open.length);
	});
}
