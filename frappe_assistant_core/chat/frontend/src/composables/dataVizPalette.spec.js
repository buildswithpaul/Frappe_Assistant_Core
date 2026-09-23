import { describe, it, expect } from "vitest";
import {
	QL_VIZ_SEQUENCE,
	QL_VIZ_SEQUENCE_DARK,
	vizSequence,
	vizColor,
	vizPeak,
	vizFade,
} from "./dataVizPalette";

describe("dataVizPalette", () => {
	it("anchors the light sequence on the brand teal and reserves gold for slot 4", () => {
		expect(QL_VIZ_SEQUENCE[0]).toBe("#0F6E5C");
		expect(QL_VIZ_SEQUENCE[3]).toBe("#C9A227");
	});

	it("uses brightened teal + gold for dark", () => {
		expect(QL_VIZ_SEQUENCE_DARK[0]).toBe("#2DAA8F");
		expect(QL_VIZ_SEQUENCE_DARK[3]).toBe("#D9B84A");
	});

	it("contains NO sky-blue / rainbow legacy colors", () => {
		const banned = ["#0ea5e9", "#a855f7", "#22c55e", "#ef4444", "#6366f1", "#ec4899"];
		for (const seq of [QL_VIZ_SEQUENCE, QL_VIZ_SEQUENCE_DARK]) {
			for (const c of seq) {
				expect(banned).not.toContain(c.toLowerCase());
			}
		}
	});

	it("vizSequence switches on isDark", () => {
		expect(vizSequence(false)).toBe(QL_VIZ_SEQUENCE);
		expect(vizSequence(true)).toBe(QL_VIZ_SEQUENCE_DARK);
	});

	it("vizColor wraps modulo the sequence length", () => {
		expect(vizColor(0, false)).toBe("#0F6E5C");
		expect(vizColor(QL_VIZ_SEQUENCE.length, false)).toBe(QL_VIZ_SEQUENCE[0]);
	});

	it("peak/fade resolve per theme", () => {
		expect(vizPeak(false)).toBe("#0F6E5C");
		expect(vizPeak(true)).toBe("#2DAA8F");
		expect(vizFade(false)).toBe("#9CC3B7");
		expect(vizFade(true)).toBe("#3F6E61");
	});
});
