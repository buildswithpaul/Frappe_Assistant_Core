// Quiet Ledger list-grid column count by container width.
// Breakpoints chosen so cards stay >= ~240px wide inside the 1200px max shell.
export const GRID_BREAKPOINTS = [
	{ minWidth: 1040, columns: 4 },
	{ minWidth: 780, columns: 3 },
	{ minWidth: 520, columns: 2 },
	{ minWidth: 0, columns: 1 },
];

export function columnsForWidth(width) {
	const w = Number.isFinite(width) ? width : 0;
	for (const bp of GRID_BREAKPOINTS) {
		if (w >= bp.minWidth) return bp.columns;
	}
	return 1;
}
