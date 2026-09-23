import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount } from "@vue/test-utils";
import { nextTick } from "vue";
import { setActivePinia, createPinia } from "pinia";

vi.mock("@/api/client", () => ({
	api: { notifications: { get: vi.fn(), dismiss: vi.fn().mockResolvedValue({}) } },
}));
import { api } from "@/api/client";
import { useNotificationStore } from "@/stores/notificationStore";
import NotificationBell from "@/components/notifications/NotificationBell.vue";
import NotificationCenter from "@/components/notifications/NotificationCenter.vue";

const N = (over = {}) => ({
	id: "n1", title: "t", message: "m", type: "feature", priority: "normal",
	dismissible: true, dismissed: false, action_label: null, action_url: null,
	created_at: "2026-08-01 10:00:00", ...over,
});

async function seed(items) {
	setActivePinia(createPinia());
	localStorage.clear();
	api.notifications.get.mockResolvedValue({ notifications: items, user: "a@x.com" });
	const store = useNotificationStore();
	await store.refresh();
	return store;
}

describe("NotificationBell", () => {
	it("shows unread badge; opening the center marks items seen", async () => {
		const store = await seed([N(), N({ id: "n2" })]);
		const w = mount(NotificationBell);
		expect(w.find("[data-testid='unread-badge']").text()).toBe("2");
		await w.find("[data-testid='bell-button']").trigger("click");
		expect(store.unreadCount).toBe(0);
		expect(w.find("[data-testid='unread-badge']").exists()).toBe(false);
	});
});

describe("NotificationCenter", () => {
	it("lists all items, outages pinned first, dismissed muted not removed", async () => {
		await seed([
			N({ id: "a", created_at: "2026-08-02 10:00:00" }),
			N({ id: "dis", dismissed: true }),
			N({ id: "out", type: "outage", dismissible: false }),
		]);
		const w = mount(NotificationCenter, { props: { open: true } });
		const items = w.findAll("[data-testid='center-item']");
		expect(items.length).toBe(3);
		expect(items[0].attributes("data-id")).toBe("out");
		expect(w.find("[data-id='dis']").classes()).toContain("is-dismissed");
		expect(w.find("[data-id='dis'] [data-testid='item-dismiss']").exists()).toBe(false);
		expect(w.find("[data-id='out'] [data-testid='item-dismiss']").exists()).toBe(false);
	});

	it("per-item dismiss calls the store; Mark all read does NOT dismiss", async () => {
		const store = await seed([N({ id: "a" }), N({ id: "b" })]);
		const w = mount(NotificationCenter, { props: { open: true } });
		await w.find("[data-id='a'] [data-testid='item-dismiss']").trigger("click");
		expect(api.notifications.dismiss).toHaveBeenCalledWith("a");
		await w.find("[data-testid='mark-all-read']").trigger("click");
		expect(store.unreadCount).toBe(0);
		expect(store.activeNotifications.map((n) => n.id)).toEqual(["b"]);
	});
});

// These mount with attachTo: document.body so events dispatched on the
// bell button actually bubble to `document`, where the outside-click/Escape
// listeners live (owned by NotificationBell, not NotificationCenter — see
// NotificationBell.vue). Without attachTo the wrapper tree is detached and
// those listeners never fire, so this is the only place that exercises the
// open/close behavior and the Escape path at all.
//
// HONEST LIMITATION: these tests do NOT reproduce, and cannot fail against,
// the two production races the fix addresses:
//
// 1. Bell click self-closing the panel it just opened. This only manifested
//    with real, OS-level Chromium input dispatch, where the mousedown/
//    mouseup/click sequence spans multiple tasks and lets Vue's microtask-
//    scheduled re-render land *before* the click's bubble phase reaches
//    `document`. jsdom's `.trigger()` dispatches synchronously in a single
//    task, so Vue's re-render is provably still pending when the bubble
//    reaches `document` — meaning even the OLD, panel-only containment
//    check (`panelRef.value` was null at that point) could never self-close
//    here.
// 2. Dismissing an item closing the whole panel. A real click on an item's
//    own dismiss button was observed, live, removing that button from the
//    DOM (store.dismiss mutates state synchronously, and in the same real-
//    Chromium multi-task pipeline as (1), the re-render can land before the
//    click finishes bubbling) *before* an outside-click check listening on
//    "click" ran — and contains() on an already-detached node is always
//    false, reading as "outside". jsdom's synchronous dispatch again can't
//    reproduce the race that exposed this.
//
// Both were confirmed against real Chromium via Playwright as part of this
// fix (see task-13-report.md) — that is the only way this class of bug is
// actually caught. What CAN be verified here, and what actually changed, is
// structural: the containment boundary is the wrapper that owns both the
// trigger and the panel (not the panel alone, bound once at mount, timing-
// independent by construction — tested below), and the outside-check listens
// on "mousedown" rather than "click", which by DOM event ordering always
// fires before any click handler's own DOM mutations — a guarantee the spec
// makes, not a timing race, so it holds in jsdom exactly as in a real
// browser (also tested below).
// Regression guard for the AR-outage fallback bug: the 6-hour heartbeat
// cron blob (apps/assistant_runtime/assistant_runtime/api/heartbeat.py,
// pre-fix) emitted exactly this 7-key shape — no dismissible, no
// dismissed, no created_at. Seeded verbatim, not via the N() helper,
// because every other test in this file supplies dismissible explicitly
// and so cannot exercise the missing-key case at all.
const HEARTBEAT_SHAPED_OUTAGE = {
	id: "hb-outage",
	title: "Degraded service",
	message: "AR is unreachable",
	type: "outage",
	action_label: null,
	action_url: null,
	priority: "high",
};

describe("NotificationCenter with a heartbeat-shaped fallback payload", () => {
	it("shows no dismiss affordance for an item missing the dismissible key", async () => {
		await seed([HEARTBEAT_SHAPED_OUTAGE]);
		const w = mount(NotificationCenter, { props: { open: true } });
		expect(w.find("[data-id='hb-outage'] [data-testid='item-dismiss']").exists()).toBe(false);
	});
});

describe("NotificationBell outside-click / Escape (attached to document)", () => {
	let wrapper;

	afterEach(() => {
		wrapper?.unmount();
		wrapper = undefined;
	});

	async function openBell(items) {
		await seed(items);
		wrapper = mount(NotificationBell, { attachTo: document.body });
		await wrapper.find("[data-testid='bell-button']").trigger("click");
		return wrapper;
	}

	it("the containment boundary wraps both the trigger and the panel", async () => {
		const w = await openBell([N()]);
		const wrap = w.find(".notif-bell-wrap");
		expect(wrap.find("[data-testid='bell-button']").exists()).toBe(true);
		expect(wrap.find("[role='dialog']").exists()).toBe(true);
	});

	it("clicking the bell opens the panel and it stays open (no self-close)", async () => {
		const w = await openBell([N()]);
		expect(w.find("[role='dialog']").exists()).toBe(true);
	});

	it("a mousedown on an unrelated document element closes the panel", async () => {
		const w = await openBell([N()]);
		expect(w.find("[role='dialog']").exists()).toBe(true);

		const outside = document.createElement("div");
		document.body.appendChild(outside);
		outside.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
		await nextTick();

		expect(w.find("[role='dialog']").exists()).toBe(false);
		document.body.removeChild(outside);
	});

	it("a mousedown inside the panel does not close it", async () => {
		const w = await openBell([N()]);
		w.find("[data-testid='mark-all-read']").element.dispatchEvent(
			new MouseEvent("mousedown", { bubbles: true })
		);
		await nextTick();

		expect(w.find("[role='dialog']").exists()).toBe(true);
	});

	// Pins the mechanism behind fixing race (2) above: mousedown on the
	// dismiss button (button still attached, panel must stay open) followed
	// by the click that actually removes it (store.dismiss + v-if) must not
	// retroactively close the panel — there is no second outside-check to
	// re-run once the button is gone.
	it("dismissing an item does not close the panel, even though dismissing removes that item's own button", async () => {
		const w = await openBell([N({ id: "a" }), N({ id: "b" })]);
		const dismissBtn = w.find("[data-id='a'] [data-testid='item-dismiss']").element;

		dismissBtn.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
		await nextTick();
		expect(w.find("[role='dialog']").exists()).toBe(true);

		dismissBtn.dispatchEvent(new MouseEvent("click", { bubbles: true }));
		await nextTick();

		expect(w.find("[data-id='a'] [data-testid='item-dismiss']").exists()).toBe(false);
		expect(w.find("[role='dialog']").exists()).toBe(true);
	});

	it("Escape closes the panel", async () => {
		const w = await openBell([N()]);
		expect(w.find("[role='dialog']").exists()).toBe(true);

		document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
		await nextTick();

		expect(w.find("[role='dialog']").exists()).toBe(false);
	});
});
