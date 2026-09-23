import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

vi.mock("@/api/client", () => ({
	api: { notifications: { get: vi.fn(), dismiss: vi.fn().mockResolvedValue({}) } },
}));
import { api } from "@/api/client";
import { useNotificationStore } from "@/stores/notificationStore";
import OutageBanner from "@/components/notifications/OutageBanner.vue";
import HighPriorityBanner from "@/components/notifications/HighPriorityBanner.vue";
import { safeActionUrl } from "@/components/notifications/typeMeta";

const N = (over = {}) => ({
	id: "n1", title: "Big outage", message: "**bold** details", type: "outage",
	priority: "high", dismissible: false, dismissed: false,
	action_label: null, action_url: null, created_at: "2026-08-01 10:00:00", ...over,
});

async function seed(items) {
	setActivePinia(createPinia());
	api.notifications.get.mockResolvedValue({ notifications: items, user: "a@x.com" });
	const store = useNotificationStore();
	await store.refresh();
	return store;
}

// module-scoped: dismiss() persists to localStorage keyed by user, so it
// must be cleared before every test, not just within one describe block —
// otherwise a notification id dismissed in one test (e.g. "h1") reads back
// as already-dismissed in a later test that reuses the same id.
beforeEach(() => localStorage.clear());

describe("OutageBanner", () => {
	it("renders sanitized markdown, no dismiss button when non-dismissible", async () => {
		await seed([N({ message: "**bold** <img src=x onerror=alert(1)>" })]);
		const w = mount(OutageBanner);
		expect(w.html()).toContain("<strong>bold</strong>");
		expect(w.html()).not.toContain("onerror");
		expect(w.html()).not.toContain("<img");
		expect(w.find("[data-testid='outage-dismiss']").exists()).toBe(false);
		expect(w.attributes("aria-live") ?? w.find("[aria-live]").exists()).toBeTruthy();
	});

	it("maintenance is dismissible", async () => {
		const store = await seed([N({ type: "maintenance", dismissible: true })]);
		const w = mount(OutageBanner);
		await w.find("[data-testid='outage-dismiss']").trigger("click");
		expect(store.outageNotifications.length).toBe(0);
	});
});

describe("HighPriorityBanner", () => {
	it("shows only high-priority non-outage; dismiss removes", async () => {
		const store = await seed([
			N({ id: "h1", type: "feature", priority: "high", dismissible: true }),
			N({ id: "l1", type: "promotion", priority: "low", dismissible: true }),
		]);
		const w = mount(HighPriorityBanner);
		expect(w.text()).toContain("Big outage");
		await w.find("[data-testid='banner-dismiss']").trigger("click");
		expect(store.bannerNotification).toBeNull();
		expect(api.notifications.dismiss).toHaveBeenCalledWith("h1");
	});

	// Regression guard: aria-live must sit on a wrapper that exists BEFORE
	// the banner content does, or the region and its text arrive in the
	// same DOM mutation and assistive tech never announces it (the region
	// has to already be there for the mutation to be observed). Assert the
	// wrapper's own attribute, not `w.find("[aria-live]")`, which would
	// also pass if aria-live were still on the v-if'd content.
	it("aria-live region exists on the wrapper even with no banner showing", async () => {
		await seed([]);
		const w = mount(HighPriorityBanner);
		expect(w.attributes("aria-live")).toBe("polite");
		expect(w.find(".banner").exists()).toBe(false);
	});

	it("aria-live region stays on the wrapper once a banner is showing", async () => {
		await seed([N({ id: "h1", type: "feature", priority: "high", dismissible: true })]);
		const w = mount(HighPriorityBanner);
		expect(w.attributes("aria-live")).toBe("polite");
		expect(w.find(".banner").attributes("aria-live")).toBeUndefined();
	});
});

describe("HighPriorityBanner transition", () => {
	it("renders a long wrapping title and message in full", async () => {
		const title = "A notification title long enough to wrap across two lines on a narrow viewport";
		const message = "**Extra detail** that pushes the row well past a single line so wrapping actually engages";
		await seed([N({ id: "h1", type: "feature", priority: "high", dismissible: true, title, message })]);
		const w = mount(HighPriorityBanner);
		expect(w.text()).toContain(title);
		expect(w.html()).toContain("<strong>Extra detail</strong>");
	});

	// jsdom has no layout engine, so a mounted assertion alone can't detect a
	// CSS height clip — it verifies content presence, not paint. The actual
	// regression guard is the CSS itself: the transition must animate only
	// opacity/transform (as OutageBanner already does), never max-height +
	// overflow:hidden, or wrapped content is invisible mid-transition.
	it("transition CSS does not cap height (would clip wrapped content mid-animation)", () => {
		const __dirname = dirname(fileURLToPath(import.meta.url));
		const source = readFileSync(join(__dirname, "./HighPriorityBanner.vue"), "utf8");
		const activeBlock = source.match(
			/\.banner-slide-enter-active,\s*\.banner-slide-leave-active\s*\{([\s\S]*?)\}/
		);
		expect(activeBlock).not.toBeNull();
		expect(activeBlock[1]).not.toMatch(/max-height/);
		expect(activeBlock[1]).not.toMatch(/overflow:\s*hidden/);
	});
});

describe("safeActionUrl", () => {
	it("filters schemes", () => {
		expect(safeActionUrl("javascript:alert(1)")).toBe("");
		expect(safeActionUrl("https://x.com/a")).toBe("https://x.com/a");
		expect(safeActionUrl("/app/page")).toBe("/app/page");
		expect(safeActionUrl("//evil.com")).toBe("");
		expect(safeActionUrl("mailto:a@b.com")).toBe("mailto:a@b.com");
	});
});
