import { describe, expect, it } from "vitest";
import { fillPageAsk } from "./pageAskFill";

describe("fillPageAsk", () => {
	it("fills doctype and name", () => {
		expect(fillPageAsk("What changed on {doctype} {name}? {name}", { doctype: "Sales Invoice", name: "SINV-0001" })).toBe(
			"What changed on Sales Invoice SINV-0001? SINV-0001"
		);
	});

	it("drops a name ask without a name", () => {
		expect(fillPageAsk("Summarise this {doctype}: {name}", { doctype: "Sales Invoice" })).toBeNull();
	});

	it("list asks need only doctype", () => {
		expect(fillPageAsk("Summarise this {doctype} list", { doctype: "Sales Invoice" })).toBe(
			"Summarise this Sales Invoice list"
		);
		expect(fillPageAsk("Summarise this {doctype} list", {})).toBeNull();
	});
});
