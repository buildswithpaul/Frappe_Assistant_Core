// Quiet Ledger data-viz palette (spec §2.4) — teal-anchored, gold + warm neutrals.
// Defined ONCE; every chart imports from here. No echarts rainbow.
export const QL_VIZ_SEQUENCE = [
	"#0F6E5C", // teal (brand accent)
	"#3C8C72", // teal-light
	"#6BAA8C", // teal-muted
	"#C9A227", // gold (money/consequence)
	"#B8791A", // amber
	"#8A857C", // warm neutral
	"#57534C", // warm dark neutral
	"#A88B4A", // muted gold-neutral
];

// Dark-theme variant (brightened teal + gold per §2.1 dark overrides).
export const QL_VIZ_SEQUENCE_DARK = [
	"#2DAA8F", // teal brightened
	"#4FBFA4",
	"#7FD0BB",
	"#D9B84A", // gold brightened
	"#C99A3F",
	"#B7B2A4",
	"#8C877B",
	"#C7AE63",
];

// Single-series highlight (e.g. peak day bar): full accent vs faded same-hue.
export const QL_VIZ_PEAK = { light: "#0F6E5C", dark: "#2DAA8F" };
export const QL_VIZ_FADE = { light: "#9CC3B7", dark: "#3F6E61" };

export function vizSequence(isDark) {
	return isDark ? QL_VIZ_SEQUENCE_DARK : QL_VIZ_SEQUENCE;
}
export function vizColor(index, isDark) {
	const seq = vizSequence(isDark);
	return seq[index % seq.length];
}
export function vizPeak(isDark) {
	return isDark ? QL_VIZ_PEAK.dark : QL_VIZ_PEAK.light;
}
export function vizFade(isDark) {
	return isDark ? QL_VIZ_FADE.dark : QL_VIZ_FADE.light;
}
