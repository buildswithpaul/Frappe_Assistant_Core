import { describe, it, expect, beforeAll, beforeEach, afterEach, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import * as Rules from "@/components/spotlight/spotlightRules";

const spotlightJs = resolve(process.cwd(), "../../public/chat/widget/widget_spotlight.js");
let W;

/**
 * jQuery is not a dependency of this package, so the DOM tests drive the
 * widget through the few jQuery methods it uses: find, append, prepend,
 * remove, on.
 */
class Wrapped {
	constructor(els) {
		this.els = els;
	}
	find(sel) {
		return new Wrapped(this.els.flatMap((el) => [...el.querySelectorAll(sel)]));
	}
	remove() {
		this.els.forEach((el) => el.remove());
		return this;
	}
	append(html) {
		this.els.forEach((el) => el.insertAdjacentHTML("beforeend", html));
		return this;
	}
	prepend(html) {
		this.els.forEach((el) => el.insertAdjacentHTML("afterbegin", html));
		return this;
	}
	scrollTop(value) {
		this.els.forEach((el) => {
			el.scrollTop = value;
		});
		return this;
	}
	on(event, handler) {
		this.els.forEach((el) => el.addEventListener(event, handler));
		return this;
	}
}

beforeAll(() => {
	globalThis.__ = (s, args) => (args ? s.replace(/\{(\d+)\}/g, (_m, i) => args[i]) : s);
	// eslint-disable-next-line no-new-func
	new Function(readFileSync(spotlightJs, "utf8"))();
	W = window.FACOWidgetSpotlight;
});

beforeEach(() => localStorage.clear());

const NOW = new Date(2026, 9, 3, 12);
const STATUSES = [
	null,
	{ is_unlimited: true },
	{ is_fallback: true, credits_exhausted: true },
	{ credits_exhausted: true, billing_cycle_start: "2026-09-24" },
	{ credits_exhausted: true, billing_cycle_start: "2026-01-31" },
	{ percentage_used: 85, plan: "Free", quota_remaining: 150, billing_cycle_start: "2026-09-24", upgrade: { plan: "Basic", benefits: ["a"] } },
	{ percentage_used: 85, upgrade: { plan: "Basic" } },
	{ percentage_used: 85, upgrade: null },
	{ percentage_used: 85 },
	{ percentage_used: 100, in_overage: true },
	{ percentage_used: 50 },
];
const LISTS = [
	[],
	[{ id: "a", display_style: "banner" }],
	[
		{ id: "b", display_style: "modal", dismissed: true },
		{ id: "c", display_style: "modal", title: "t", action_label: "Go", action_route: "/x" },
	],
	[{ id: "d", display_style: "modal", title: "t", action_route: "//evil.com", action_url: "https://ok.com", highlights: ["h"], media_url: "/m.mp4", media_type: "video" }],
	[{ id: "e", display_style: "modal", title: "t", action_label: "  ", action_route: "/a b", action_url: "javascript:alert(1)" }],
	[{ id: "f", display_style: "modal", title: "t", action_url: "https://x.io/p" }],
];

describe("parity with the SPA rules", () => {
	it("keys and dates match", () => {
		expect(W.daily_key("u", "widget")).toBe(Rules.DAILY_KEY("u", "widget"));
		expect(W.daily_key("u", "spa")).toBe(Rules.DAILY_KEY("u", "spa"));
		expect(W.quota_key("u", "2026-09-24", 80)).toBe(Rules.QUOTA_KEY("u", "2026-09-24", 80));
		expect(W.local_date(NOW)).toBe(Rules.localDate(NOW));
		for (const s of STATUSES) expect(W.cycle_start(s, NOW)).toBe(Rules.cycleStart(s, NOW));
	});

	it("formats the reset date identically", () => {
		expect(W.format_reset_date("2026-10-26")).toBe(Rules.formatResetDate("2026-10-26"));
		expect(W.format_reset_date("2026-10-26")).toBe("Oct 26, 2026");
	});

	it("reset date, thresholds and content match", () => {
		for (const s of STATUSES) {
			expect(W.next_reset_date(s)).toBe(Rules.nextResetDate(s));
			expect(W.quota_threshold(s)).toBe(Rules.quotaThreshold(s));
			if (Rules.quotaThreshold(s)) expect(W.quota_content(s)).toEqual(Rules.quotaContent(s));
		}
	});

	it("announcement pick and content match", () => {
		for (const l of LISTS) {
			expect(W.pick_announcement(l)).toEqual(Rules.pickAnnouncement(l));
			const n = Rules.pickAnnouncement(l);
			if (n) expect(W.announcement_content(n)).toEqual(Rules.announcementContent(n));
		}
	});
});

function fakeWidget({ admin = true, quota = null, notifications = [], ...access } = {}) {
	document.body.innerHTML = `<div id="w"><button class="faco-toggle-btn"></button><div class="faco-messages"></div></div>`;
	const root = new Wrapped([document.getElementById("w")]);
	return {
		$widget: { find: (sel) => root.find(sel) },
		quota_status: quota ? { ...quota, is_admin: admin } : null,
		spotlight_notifications: structuredClone(notifications),
		user: "owner@acme.com",
		can_use: true,
		user_setup_complete: true,
		privacy_consent_complete: true,
		...access,
	};
}

describe("widget spotlight DOM", () => {
	beforeAll(() => {
		window.frappe = { session: { user: "owner@acme.com" }, call: vi.fn(async () => ({ message: {} })) };
	});

	afterEach(() => {
		vi.restoreAllMocks();
		window.frappe.call.mockClear();
	});

	it("shows a dot when something is pending, and nothing when not", () => {
		W.update_dot(fakeWidget({ notifications: LISTS[2] }));
		expect(document.querySelector(".faco-toggle-btn .faco-spotlight-dot")).not.toBeNull();
		W.update_dot(fakeWidget());
		expect(document.querySelector(".faco-spotlight-dot")).toBeNull();
	});

	it("does not stack dots on repeated updates", () => {
		const w = fakeWidget({ notifications: LISTS[2] });
		W.update_dot(w);
		W.update_dot(w);
		expect(document.querySelectorAll(".faco-spotlight-dot")).toHaveLength(1);
	});

	it("non-admin never gets a quota card or dot", () => {
		const w = fakeWidget({ admin: false, quota: { credits_exhausted: true } });
		expect(W.pending(w)).toBeNull();
	});

	it.each([
		["cannot use the widget", { can_use: false }],
		["has not finished setup", { user_setup_complete: false }],
		["has not given privacy consent", { privacy_consent_complete: false }],
	])("nothing is pending (no dot, no card) when the user %s", (_label, access) => {
		const w = fakeWidget({ quota: { credits_exhausted: true }, notifications: LISTS[2], ...access });
		expect(W.pending(w)).toBeNull();
		W.update_dot(w);
		expect(document.querySelector(".faco-spotlight-dot")).toBeNull();
	});

	it("labels the card's dismiss button differently from the panel's Close", () => {
		const w = fakeWidget({ quota: { credits_exhausted: true } });
		W.render_in_panel(w);
		expect(document.querySelector("[data-spot='dismiss']").getAttribute("aria-label")).toBe("Dismiss");
	});

	it("quota outranks an announcement", () => {
		const w = fakeWidget({ quota: { percentage_used: 85 }, notifications: LISTS[2] });
		expect(W.pending(w).kind).toBe("quota");
	});

	it("an announcement already shown today is not pending again", () => {
		const w = fakeWidget({ admin: false, notifications: LISTS[2] });
		W.render_in_panel(w);
		expect(localStorage.getItem("fac_spotlight_last_shown:owner@acme.com:widget")).toBe(W.local_date());
		expect(W.pending(w)).toBeNull();
	});

	it("does not consume the SPA's showing", () => {
		const w = fakeWidget({ admin: false, notifications: LISTS[2] });
		W.render_in_panel(w);
		expect(localStorage.getItem("fac_spotlight_last_shown:owner@acme.com:spa")).toBeNull();
	});

	it("is unaffected by a stamp the SPA left today", () => {
		const w = fakeWidget({ admin: false, notifications: LISTS[2] });
		localStorage.setItem("fac_spotlight_last_shown:owner@acme.com:spa", W.local_date());
		expect(W.pending(w)).not.toBeNull();
	});

	it("renders the card in the panel, and Not now dismisses it via the FAC endpoint", async () => {
		const w = fakeWidget({ admin: false, notifications: LISTS[2] });
		W.render_in_panel(w);
		const card = document.querySelector(".faco-messages .faco-spotlight-card");
		expect(card.textContent).toContain("Go");
		card.querySelector("[data-spot='secondary']").click();
		await Promise.resolve();
		expect(window.frappe.call).toHaveBeenCalledWith(
			expect.objectContaining({
				method: "frappe_assistant_core.chat.api.notifications.dismiss_notification",
				args: { notification_id: "c" },
			}),
		);
		expect(document.querySelector(".faco-spotlight-card")).toBeNull();
	});

	it("rendering a card leaves the conversation scroll position alone", () => {
		const w = fakeWidget({ quota: { credits_exhausted: true } });
		const spy = vi.spyOn(document.querySelector(".faco-messages"), "scrollTop", "set");
		W.render_in_panel(w);
		expect(spy).not.toHaveBeenCalled();
	});

	it("rendering an announcement clears the launcher dot", () => {
		const w = fakeWidget({ admin: false, notifications: LISTS[2] });
		W.update_dot(w);
		expect(document.querySelector(".faco-spotlight-dot")).not.toBeNull();
		W.render_in_panel(w);
		expect(document.querySelector(".faco-spotlight-dot")).toBeNull();
	});

	it("rendering again replaces the card instead of stacking", () => {
		const w = fakeWidget({ admin: false, notifications: LISTS[2] });
		W.render_in_panel(w);
		W.render_in_panel(w, W.announcement_content(LISTS[2][1]));
		expect(document.querySelectorAll(".faco-spotlight-card")).toHaveLength(1);
	});

	it("primary opens the SPA route in a new tab and records the cycle key", () => {
		const open = vi.spyOn(window, "open").mockImplementation(() => null);
		const w = fakeWidget({
			quota: { percentage_used: 85, billing_cycle_start: "2026-09-24", upgrade: { plan: "Basic", benefits: [] } },
		});
		W.render_in_panel(w);
		document.querySelector("[data-spot='primary']").click();
		expect(open).toHaveBeenCalledWith("/copilot/settings/billing?tab=plans", "_blank", "noopener");
		expect(localStorage.getItem("fac_quota_moment:owner@acme.com:2026-09-24:80")).toBe("1");
		expect(document.querySelector(".faco-spotlight-card")).toBeNull();
	});

	it("opens http(s) announcement URLs and a primary with no target just dismisses", () => {
		const open = vi.spyOn(window, "open").mockImplementation(() => null);
		const w = fakeWidget({ admin: false, notifications: [LISTS[5][0]] });
		W.render_in_panel(w);
		document.querySelector("[data-spot='primary']").click();
		expect(open).toHaveBeenCalledWith("https://x.io/p", "_blank", "noopener");

		open.mockClear();
		localStorage.clear();
		const bare = fakeWidget({ admin: false, notifications: [LISTS[4][0]] });
		W.render_in_panel(bare);
		expect(document.querySelector("[data-spot='primary']").textContent).toBe("Got it");
		document.querySelector("[data-spot='primary']").click();
		expect(open).not.toHaveBeenCalled();
		expect(document.querySelector(".faco-spotlight-card")).toBeNull();
	});

	it("escapes text", () => {
		const w = fakeWidget({
			admin: false,
			notifications: [{ id: "x", display_style: "modal", title: "<img src=x onerror=alert(1)>", action_label: "Go", action_route: "/x" }],
		});
		W.render_in_panel(w);
		expect(document.querySelector(".faco-spotlight-card img[src='x']")).toBeNull();
		expect(document.querySelector(".faco-spot-title").textContent).toContain("<img");
	});

	it("autoplays video unless reduced motion is requested", () => {
		const n = [{ id: "v", display_style: "modal", title: "t", media_url: "/m.mp4", media_type: "video" }];
		window.matchMedia = vi.fn(() => ({ matches: false }));
		W.render_in_panel(fakeWidget({ admin: false, notifications: n }));
		expect(document.querySelector("video").hasAttribute("autoplay")).toBe(true);

		localStorage.clear();
		window.matchMedia = vi.fn(() => ({ matches: true }));
		W.render_in_panel(fakeWidget({ admin: false, notifications: n }));
		const video = document.querySelector("video");
		expect(video.hasAttribute("autoplay")).toBe(false);
		expect(video.hasAttribute("controls")).toBe(true);
		delete window.matchMedia;
	});

	it("renders the overage notice as one line", () => {
		const w = fakeWidget();
		W.render_notice(w, "Hello <b>");
		W.render_notice(w, "Again");
		const notices = document.querySelectorAll(".faco-spotlight-notice");
		expect(notices).toHaveLength(1);
		expect(notices[0].textContent).toBe("Again");
	});

	it("refresh stores notifications from the FAC endpoint and sets the dot", async () => {
		window.frappe.call.mockResolvedValueOnce({ message: { notifications: LISTS[2] } });
		const w = fakeWidget({ admin: false });
		await W.refresh(w);
		expect(w.spotlight_notifications).toEqual(LISTS[2]);
		expect(document.querySelector(".faco-spotlight-dot")).not.toBeNull();
	});
});
