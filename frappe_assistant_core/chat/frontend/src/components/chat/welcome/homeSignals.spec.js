import { describe, expect, it } from "vitest";
import { mergeSignals } from "./homeSignals";

const item = (id, tone) => ({ id, tone, source: "S", count: 1, title: id, detail: "", ask: id });

describe("homeSignals", () => {
	it("mergeSignals puts danger before warning", () => {
		const out = mergeSignals([item("n", "neutral"), item("w", "warning"), item("d", "danger")], null, 5);
		expect(out.map((i) => i.id)).toEqual(["d", "w", "n"]);
	});

	it("mergeSignals caps", () => {
		const out = mergeSignals([item("a", "danger"), item("b", "warning"), item("c", "neutral")], null, 2);
		expect(out.map((i) => i.id)).toEqual(["a", "b"]);
	});

	it("attention item leads the dangers", () => {
		const att = { ...item("failed_workflows", "danger"), href: "/agents" };
		const out = mergeSignals([item("d1", "danger"), item("w", "warning")], att, 3);
		expect(out.map((i) => i.id)).toEqual(["failed_workflows", "d1", "w"]);
	});

	it("null attention is ignored", () => {
		const out = mergeSignals([item("a", "warning")], null, 3);
		expect(out.map((i) => i.id)).toEqual(["a"]);
	});
});
