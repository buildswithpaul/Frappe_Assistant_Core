import { afterEach, describe, expect, it, vi } from "vitest";
import { createRouterShim } from "./routerShim.js";

describe("router shim", () => {
	afterEach(() => vi.restoreAllMocks());

	// The credit meter pushes this from the Desk widget, where there is no FAC Chat router.
	it("opens My usage in FAC Chat instead of navigating", async () => {
		const open = vi.spyOn(window, "open").mockReturnValue(null);
		const router = createRouterShim();
		await router.push({ path: "/analytics", query: { view: "me" } });
		expect(open).toHaveBeenCalledWith("/copilot/analytics?view=me", "_blank", "noopener");
		expect(router.currentRoute.value.fullPath).toBe("/");
	});
});
