import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import FirstRunStarters from "./FirstRunStarters.vue";

const tile = (description, kind) => ({ name: description, description, kind });
const make = (tiles) => mount(FirstRunStarters, { props: { tiles } });
const summary = (w) =>
	w
		.findAll(".frs-card")
		.map((c) => [
			c.find(".frs-label").exists() ? c.find(".frs-label").text() : null,
			c.find(".frs-text").text(),
		]);

describe("FirstRunStarters", () => {
	it("labels each card by what the tile produces, not by position", () => {
		const w = make([tile("D?", "do"), tile("S?", "see"), tile("F?", "find")]);
		expect(summary(w)).toEqual([
			["See it", "S?"],
			["Find it", "F?"],
			["Do it", "D?"],
		]);
	});

	it("fills a missing kind from the remaining tiles without a label", () => {
		const w = make([tile("S?", "see"), tile("F?", "find"), tile("X?", undefined)]);
		expect(summary(w)).toEqual([
			["See it", "S?"],
			["Find it", "F?"],
			[null, "X?"],
		]);
	});

	it("emits pick with the tile text", async () => {
		const w = make([tile("S?", "see")]);
		await w.find(".frs-card").trigger("click");
		expect(w.emitted("pick")).toEqual([["S?"]]);
	});

	it("previews a spare tile as its own kind", () => {
		const w = make([tile("S?", "see"), tile("F?", "find"), tile("S2?", "see")]);
		expect(w.findAll(".frs-preview")[2].classes()).toContain("frs-preview--see");
		expect(summary(w)[2]).toEqual([null, "S2?"]);
	});

	it("keeps all three labels for a two-lens interleaved list", () => {
		const w = make([
			tile("A find", "find"),
			tile("S find", "find"),
			tile("A see", "see"),
			tile("S see", "see"),
			tile("A do", "do"),
			tile("S do", "do"),
		]);
		expect(summary(w)).toEqual([
			["See it", "A see"],
			["Find it", "A find"],
			["Do it", "A do"],
		]);
	});

	it("does not let a personalized tile without a kind steal a labelled slot", () => {
		const w = make([
			tile("P1", undefined),
			tile("P2", undefined),
			tile("S?", "see"),
			tile("F?", "find"),
			tile("D?", "do"),
		]);
		expect(summary(w)).toEqual([
			["See it", "S?"],
			["Find it", "F?"],
			["Do it", "D?"],
		]);
	});
});
