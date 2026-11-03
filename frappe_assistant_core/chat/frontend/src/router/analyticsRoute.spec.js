import { describe, expect, it } from "vitest";
import router from "@/router";
import { requireAdmin } from "./index";

const findRoute = (path) => router.getRoutes().find((r) => r.path === path);

describe("analytics routes", () => {
	it("opens /analytics to every member", () => {
		expect(findRoute("/analytics").beforeEnter).toBeUndefined();
	});

	it("keeps billing admin-only", () => {
		expect(findRoute("/settings/billing").beforeEnter).toBe(requireAdmin);
	});
});
