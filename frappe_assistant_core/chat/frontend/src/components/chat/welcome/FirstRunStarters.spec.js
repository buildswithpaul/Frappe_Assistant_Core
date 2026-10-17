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
});
