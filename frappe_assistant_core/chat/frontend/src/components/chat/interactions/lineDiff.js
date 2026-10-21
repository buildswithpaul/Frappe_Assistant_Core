/**
 * Line diff between two texts, for the approval card's old-vs-new code view.
 * Returns ordered rows of { type: "same" | "del" | "add", text }, or null when the texts
 * are too large to diff (the table below is lines-old x lines-new in memory).
 */
export const MAX_DIFF_CELLS = 4_000_000;

export function lineDiff(oldText, newText) {
	const a = oldText === "" ? [] : oldText.split("\n");
	const b = newText === "" ? [] : newText.split("\n");
	if (a.length * b.length > MAX_DIFF_CELLS) return null;

	// lcs[i][j] = length of the longest common subsequence of a[i:] and b[j:].
	const lcs = Array.from({ length: a.length + 1 }, () => new Uint32Array(b.length + 1));
	for (let i = a.length - 1; i >= 0; i--) {
		for (let j = b.length - 1; j >= 0; j--) {
			lcs[i][j] = a[i] === b[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
		}
	}

	const rows = [];
	let i = 0;
	let j = 0;
	while (i < a.length && j < b.length) {
		if (a[i] === b[j]) {
			rows.push({ type: "same", text: a[i] });
			i++;
			j++;
		} else if (lcs[i + 1][j] >= lcs[i][j + 1]) {
			rows.push({ type: "del", text: a[i++] });
		} else {
			rows.push({ type: "add", text: b[j++] });
		}
	}
	while (i < a.length) rows.push({ type: "del", text: a[i++] });
	while (j < b.length) rows.push({ type: "add", text: b[j++] });
	return rows;
}
