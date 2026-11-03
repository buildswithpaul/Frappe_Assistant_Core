import { describe, expect, it } from "vitest";
import { resolveUsageView } from "./usageView";

describe("resolveUsageView", () => {
	it("always gives a member their own usage", () => {
		expect(resolveUsageView(false, {})).toBe("me");
		expect(resolveUsageView(false, { view: "workspace" })).toBe("me");
	});

	it("gives an admin the workspace unless they ask for their own", () => {
		expect(resolveUsageView(true, {})).toBe("workspace");
		expect(resolveUsageView(true, { view: "me" })).toBe("me");
		expect(resolveUsageView(true, { view: "bogus" })).toBe("workspace");
	});
});
