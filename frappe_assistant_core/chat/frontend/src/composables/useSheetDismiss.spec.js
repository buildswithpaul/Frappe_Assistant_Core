import { describe, it, expect } from "vitest";
import { shouldDismissSheet, SHEET_DISMISS_PX } from "./useSheetDismiss.js";

describe("shouldDismissSheet", () => {
	it("stays open for a short drag", () => {
		expect(shouldDismissSheet(0)).toBe(false);
		expect(shouldDismissSheet(SHEET_DISMISS_PX - 1)).toBe(false);
	});

	it("closes once the drag crosses the threshold", () => {
		expect(shouldDismissSheet(SHEET_DISMISS_PX)).toBe(true);
		expect(shouldDismissSheet(200)).toBe(true);
	});
});
