import { describe, it, expect } from "vitest";
import { resolveIndexMode, INDEX_MIN_EXCHANGES } from "./useLedgerIndex.js";

const base = {
	viewportWidth: 1700, shellWidth: 1440, railDockWidth: 0,
	columnWidth: 960, completedExchanges: 5, collapsed: false,
};

describe("resolveIndexMode", () => {
	it("full when there is room", () => {
		expect(resolveIndexMode(base)).toBe("full"); // 1440-0-960-48 = 432 ≥ 240
	});
	it("spine when the rail eats the room", () => {
		expect(resolveIndexMode({ ...base, railDockWidth: 300 })).toBe("spine"); // 132 ≥ 28
	});
	it("hidden when even the spine cannot fit", () => {
		expect(resolveIndexMode({ ...base, shellWidth: 1020, columnWidth: 960 })).toBe("hidden"); // 12
	});
	it("hidden under the viewport floor and under the exchange gate", () => {
		expect(resolveIndexMode({ ...base, viewportWidth: 1279 })).toBe("hidden");
		expect(resolveIndexMode({ ...base, completedExchanges: INDEX_MIN_EXCHANGES - 1 })).toBe("hidden");
	});
	it("user collapse forces spine even with room", () => {
		expect(resolveIndexMode({ ...base, collapsed: true })).toBe("spine");
	});
	it("cozy column frees room on a laptop", () => {
		expect(resolveIndexMode({ ...base, shellWidth: 1180, columnWidth: 720, railDockWidth: 0 })).toBe("full"); // 412
	});
});
