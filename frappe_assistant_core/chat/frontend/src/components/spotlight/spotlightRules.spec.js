import { describe, it, expect, vi, beforeEach } from "vitest";
import {
	cycleStart, quotaThreshold, pickAnnouncement, quotaContent, announcementContent,
	formatResetDate, nextResetDate, localDate, storage, PLANS_ROUTE, CREDITS_ROUTE, DAILY_KEY,
} from "./spotlightRules";

const NOW = new Date(2026, 9, 3, 12, 0, 0); // 3 Oct 2026 local

describe("quotaThreshold", () => {
	it("is 0 for missing, unlimited or fallback status", () => {
		expect(quotaThreshold(null)).toBe(0);
		expect(quotaThreshold({ is_unlimited: true, percentage_used: 99 })).toBe(0);
		expect(quotaThreshold({ is_fallback: true, credits_exhausted: true })).toBe(0);
	});
	it("is 100 only when every credit is gone", () => {
		expect(quotaThreshold({ credits_exhausted: true, percentage_used: 100 })).toBe(100);
	});
	it("is 80 at or above 80% unless prepaid credits are covering", () => {
		expect(quotaThreshold({ percentage_used: 80 })).toBe(80);
		expect(quotaThreshold({ percentage_used: 100, in_overage: true })).toBe(0);
		expect(quotaThreshold({ percentage_used: 79.9 })).toBe(0);
	});
});

describe("cycleStart / nextResetDate", () => {
	it("uses AR's cycle start, else the first of the month", () => {
		expect(cycleStart({ billing_cycle_start: "2026-09-24 00:00:00" }, NOW)).toBe("2026-09-24");
		expect(cycleStart({}, NOW)).toBe("2026-10-01");
	});
	it("resets one month after the cycle start", () => {
		expect(nextResetDate({ billing_cycle_start: "2026-09-24" })).toBe("2026-10-24");
		expect(nextResetDate({})).toBeNull();
	});
	it("clamps month-end overflow", () => {
		expect(nextResetDate({ billing_cycle_start: "2026-01-31" })).toBe("2026-02-28");
		expect(nextResetDate({ billing_cycle_start: "2025-12-31" })).toBe("2026-01-31");
		expect(nextResetDate({ billing_cycle_start: "2026-03-31" })).toBe("2026-04-30");
	});
	it("formats the reset date for the body copy", () => {
		expect(formatResetDate("2026-10-26")).toBe("Oct 26, 2026");
		expect(quotaContent({ percentage_used: 85, billing_cycle_start: "2026-09-26" }).body).toContain(
			"Credits reset on Oct 26, 2026.",
		);
	});
	it("localDate is the viewer's calendar day", () => {
		expect(localDate(NOW)).toBe("2026-10-03");
	});
});

describe("pickAnnouncement", () => {
	it("returns the first undismissed modal-style item", () => {
		const list = [
			{ id: "a", display_style: "banner" },
			{ id: "b", display_style: "modal", dismissed: true },
			{ id: "c", display_style: "modal" },
		];
		expect(pickAnnouncement(list).id).toBe("c");
		expect(pickAnnouncement([])).toBeNull();
		expect(pickAnnouncement(undefined)).toBeNull();
	});
});

describe("quotaContent", () => {
	const base = { plan: "Free", quota_remaining: 180, billing_cycle_start: "2026-09-24", percentage_used: 82 };
	it("pitches the next plan with highlights", () => {
		const c = quotaContent({ ...base, upgrade: { plan: "Basic", benefits: ["10,000 credits a month"] } });
		expect(c.kind).toBe("quota");
		expect(c.threshold).toBe(80);
		expect(c.eyebrow).toBe("With Basic you get");
		expect(c.highlights).toEqual(["10,000 credits a month"]);
		expect(c.primary).toEqual({ label: "See plans", route: PLANS_ROUTE });
		expect(c.secondary).toEqual({ label: "Buy credits", route: CREDITS_ROUTE });
		expect(c.body).toMatch(/180 credits left on Free/);
	});
	it("top plan offers credits only", () => {
		const c = quotaContent({ ...base, upgrade: null });
		expect(c.primary).toEqual({ label: "Buy credits", route: CREDITS_ROUTE });
		expect(c.secondary).toBeNull();
		expect(c.highlights).toEqual([]);
	});
	it("older AR (no upgrade key) still offers plans, without highlights", () => {
		const c = quotaContent(base);
		expect(c.primary.route).toBe(PLANS_ROUTE);
		expect(c.highlights).toEqual([]);
		expect(c.eyebrow).toBe("Credits");
	});
	it("100% copy", () => {
		const c = quotaContent({ ...base, credits_exhausted: true, quota_remaining: 0 });
		expect(c.threshold).toBe(100);
		expect(c.title).toBe("You've used all of this month's credits");
	});
});

describe("announcementContent", () => {
	it("maps an AR notification", () => {
		const c = announcementContent({
			id: "n1", title: "Agents", message: "Build **agents**", eyebrow: "New",
			highlights: ["One"], media_url: "https://ar/files/a.mp4", media_type: "video", media_alt: "Demo",
			action_label: "Try it", action_route: "/agents", action_url: null,
		});
		expect(c).toMatchObject({
			kind: "announcement", id: "n1", eyebrow: "New", title: "Agents",
			media: { url: "https://ar/files/a.mp4", type: "video", alt: "Demo" },
			primary: { label: "Try it", route: "/agents" },
			secondary: { label: "Not now" },
		});
	});
	it("no media gives media null; url target kept", () => {
		const c = announcementContent({ id: "n2", title: "t", action_label: "Read", action_url: "https://x.com" });
		expect(c.media).toBeNull();
		expect(c.primary).toEqual({ label: "Read", url: "https://x.com" });
	});
	it("rejects malicious route and url targets", () => {
		const c1 = announcementContent({ id: "n3", title: "t", action_label: "Go", action_route: "//evil.com" });
		expect(c1.primary).toEqual({ label: "Go" });
		const c2 = announcementContent({ id: "n4", title: "t", action_label: "Go", action_route: "https://evil" });
		expect(c2.primary).toEqual({ label: "Go" });
		const c3 = announcementContent({ id: "n5", title: "t", action_label: "Go", action_url: "javascript:alert(1)" });
		expect(c3.primary).toEqual({ label: "Go" });
	});
	it("uses 'Got it' when action_label is empty", () => {
		const c = announcementContent({ id: "n6", title: "t", action_label: "", action_route: "/test" });
		expect(c.primary).toEqual({ label: "Got it", route: "/test" });
	});
	it("no targets and no label uses 'Got it'", () => {
		const c = announcementContent({ id: "n7", title: "t", action_label: "" });
		expect(c.primary).toEqual({ label: "Got it" });
	});
});

describe("storage", () => {
	beforeEach(() => vi.restoreAllMocks());
	it("swallows localStorage errors", () => {
		vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
		vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
		expect(storage.get("k")).toBeNull();
		expect(() => storage.set("k", "v")).not.toThrow();
	});
});

describe("DAILY_KEY", () => {
	it("scopes the daily cap to one surface", () => {
		expect(DAILY_KEY("u@acme.com", "spa")).toBe("fac_spotlight_last_shown:u@acme.com:spa");
		expect(DAILY_KEY("u@acme.com", "widget")).toBe("fac_spotlight_last_shown:u@acme.com:widget");
	});

	it("keeps the two surfaces from consuming each other's showing", () => {
		expect(DAILY_KEY("u@acme.com", "spa")).not.toBe(DAILY_KEY("u@acme.com", "widget"));
	});
});
