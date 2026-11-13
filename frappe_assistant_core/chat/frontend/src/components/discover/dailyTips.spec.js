import { describe, expect, it } from "vitest";
import { TIP_ORDER, dailyTips } from "./dailyTips";
import { POWER_IDS, safeRoute, tipContent } from "./discoveryRules";

const ALL_ON = { workflowsEnabled: true, memoryEnabled: true };

describe("dailyTips", () => {
	it("one tip per feature, in the order they take turns", () => {
		expect(dailyTips(ALL_ON).map((t) => t.feature)).toEqual(["ask", "agents", "templates", "knowledge", "pages"]);
		expect(dailyTips(ALL_ON).map((t) => t.id)).toEqual(TIP_ORDER);
	});

	it("names only features FAC knows how to check, with unique ids", () => {
		for (const t of dailyTips(ALL_ON)) expect(POWER_IDS).toContain(t.feature);
		expect(new Set(TIP_ORDER).size).toBe(TIP_ORDER.length);
	});

	it("leaves out tips about features this site has switched off", () => {
		expect(dailyTips({}).map((t) => t.feature)).toEqual(["ask", "templates", "pages"]);
		expect(dailyTips({ memoryEnabled: true }).map((t) => t.feature)).toContain("knowledge");
	});

	it("every route stays inside FAC Chat, and a question is typed in, not sent", () => {
		for (const t of dailyTips(ALL_ON)) {
			if (t.action_route) expect(safeRoute(t.action_route)).toBe(t.action_route);
		}
		const ask = dailyTips(ALL_ON).find((t) => t.feature === "ask");
		expect(ask.action_route).toBe("/chat?prompt=Who%20owes%20us%20the%20most%2C%20and%20since%20when%3F");
	});

	it("each tip opens a pop-up with its words and a way to try it", () => {
		for (const t of dailyTips(ALL_ON)) {
			const content = tipContent(t);
			expect(content.title).toBe("Did you know?");
			expect(content.body).toBe(t.message);
			expect(content.primary.label).toBe(t.action_label);
		}
		// No route: Show me uses the feature's own try (the template browser, the Pages prompt).
		expect(tipContent(dailyTips(ALL_ON).find((t) => t.feature === "templates")).primary.route).toBeNull();
	});
});
