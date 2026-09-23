import { describe, it, expect, beforeEach } from "vitest";
import { loadPins, togglePin } from "./indexPins.js";

describe("index pins", () => {
	beforeEach(() => localStorage.clear());
	it("toggles a pin on and off, persisting per session", () => {
		let pins = togglePin("s1", { messageId: "m1", heading: "RAMS table" });
		expect(pins).toEqual([{ messageId: "m1", heading: "RAMS table" }]);
		expect(loadPins("s1")).toEqual(pins);
		expect(loadPins("s2")).toEqual([]);
		pins = togglePin("s1", { messageId: "m1", heading: "RAMS table" });
		expect(pins).toEqual([]);
	});
	it("survives corrupt storage", () => {
		localStorage.setItem("faco_index_pins_s1", "{nope");
		expect(loadPins("s1")).toEqual([]);
	});
});
