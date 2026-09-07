import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";

vi.mock("@/api/client", () => ({
	api: { notifications: { get: vi.fn(), dismiss: vi.fn() } },
}));
import { api } from "@/api/client";
import { useNotificationStore } from "@/stores/notificationStore";

const N = (over = {}) => ({
	id: "n1", title: "t", message: "m", type: "info", priority: "normal",
	dismissible: true, dismissed: false, action_label: null, action_url: null,
	created_at: "2026-08-01 10:00:00", ...over,
});

describe("notificationStore", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		localStorage.clear();
		vi.useFakeTimers();
		api.notifications.get.mockReset();
		api.notifications.dismiss.mockReset();
	});
	afterEach(() => vi.useRealTimers());

	it("refresh stores list and namespaces localStorage by server user", async () => {
		api.notifications.get.mockResolvedValue({ notifications: [N()], user: "a@x.com" });
		const store = useNotificationStore();
		await store.refresh();
		expect(store.notifications.length).toBe(1);
		store.markAllSeen();
		expect(JSON.parse(localStorage.getItem("fac_notif_seen:a@x.com"))).toEqual(["n1"]);
	});

	it("keeps previous list on fetch failure", async () => {
		const store = useNotificationStore();
		api.notifications.get.mockResolvedValue({ notifications: [N()], user: "a@x.com" });
		await store.refresh();
		api.notifications.get.mockRejectedValue(new Error("boom"));
		await store.refresh();
		expect(store.notifications.length).toBe(1);
	});

	it("exposes isDismissed for server and local dismissals", async () => {
		api.notifications.get.mockResolvedValue({
			notifications: [N({ id: "srv", dismissed: true }), N({ id: "loc" })],
			user: "a@x.com",
		});
		api.notifications.dismiss.mockResolvedValue({ status: "dismissed" });
		const store = useNotificationStore();
		await store.refresh();
		expect(store.isDismissed(store.notifications.find((n) => n.id === "srv"))).toBe(true);
		const loc = store.notifications.find((n) => n.id === "loc");
		expect(store.isDismissed(loc)).toBe(false);
		await store.dismiss("loc");
		expect(store.isDismissed(loc)).toBe(true);
	});

	it("derives tiers: outage, high-priority banner, unread count", async () => {
		api.notifications.get.mockResolvedValue({
			notifications: [
				N({ id: "o1", type: "outage", dismissible: false }),
				N({ id: "h1", priority: "high" }),
				N({ id: "d1", dismissed: true }),
			],
			user: "a@x.com",
		});
		const store = useNotificationStore();
		await store.refresh();
		expect(store.outageNotifications.map((n) => n.id)).toEqual(["o1"]);
		expect(store.bannerNotification.id).toBe("h1");
		expect(store.unreadCount).toBe(2); // o1 + h1; d1 is dismissed
	});

	it("dismiss is optimistic, hits the wire, and refuses non-dismissible", async () => {
		api.notifications.get.mockResolvedValue({
			notifications: [N({ id: "h1" }), N({ id: "o1", type: "outage", dismissible: false })],
			user: "a@x.com",
		});
		api.notifications.dismiss.mockResolvedValue({ status: "dismissed" });
		const store = useNotificationStore();
		await store.refresh();
		await store.dismiss("h1");
		expect(api.notifications.dismiss).toHaveBeenCalledWith("h1");
		expect(store.activeNotifications.map((n) => n.id)).toEqual(["o1"]);
		await store.dismiss("o1");
		expect(api.notifications.dismiss).toHaveBeenCalledTimes(1); // refused
	});

	it("polls every 120s and refetches on visibilitychange->visible", async () => {
		api.notifications.get.mockResolvedValue({ notifications: [], user: "a@x.com" });
		const store = useNotificationStore();
		store.startPolling();
		await vi.runOnlyPendingTimersAsync();
		const calls = api.notifications.get.mock.calls.length;
		await vi.advanceTimersByTimeAsync(120_000);
		expect(api.notifications.get.mock.calls.length).toBe(calls + 1);
		document.dispatchEvent(new Event("visibilitychange"));
		await vi.runOnlyPendingTimersAsync();
		expect(api.notifications.get.mock.calls.length).toBeGreaterThan(calls + 1);
		store.stopPolling();
		await vi.advanceTimersByTimeAsync(360_000);
		const after = api.notifications.get.mock.calls.length;
		await vi.advanceTimersByTimeAsync(120_000);
		expect(api.notifications.get.mock.calls.length).toBe(after); // timer really dead
	});

	it("dismiss() refuses a heartbeat-shaped item missing the dismissible key entirely", async () => {
		// Exact 7-key shape the pre-fix AR heartbeat fallback emitted — no
		// dismissible, no dismissed, no created_at. A hand-written fixture
		// that always sets `dismissible` (like N() above) can never catch
		// the omission bug this guards against.
		const heartbeatShaped = {
			id: "hb-outage", title: "Degraded service", message: "AR is unreachable",
			type: "outage", action_label: null, action_url: null, priority: "high",
		};
		api.notifications.get.mockResolvedValue({ notifications: [heartbeatShaped], user: "a@x.com" });
		const store = useNotificationStore();
		await store.refresh();
		await store.dismiss("hb-outage");
		expect(api.notifications.dismiss).not.toHaveBeenCalled();
		expect(store.isDismissed(store.notifications[0])).toBe(false);
	});

	it("prunes localStorage sets against the active list and survives corrupt entries", async () => {
		localStorage.setItem("fac_notif_seen:a@x.com", JSON.stringify(["gone-1", "n1"]));
		localStorage.setItem("fac_notif_dismissed:a@x.com", "{{corrupt");
		api.notifications.get.mockResolvedValue({ notifications: [N()], user: "a@x.com" });
		const store = useNotificationStore();
		await store.refresh();
		expect(JSON.parse(localStorage.getItem("fac_notif_seen:a@x.com"))).toEqual(["n1"]);
	});

	it("does not prune against a degraded (fail-soft) response, even when it is empty", async () => {
		localStorage.setItem("fac_notif_seen:a@x.com", JSON.stringify(["gone-1", "n1"]));
		localStorage.setItem("fac_notif_dismissed:a@x.com", JSON.stringify(["gone-2", "n1"]));
		// AR is down: get_notifications degrades to an empty list rather than
		// throwing (chat/api/notifications.py's fail-soft fallback). This is
		// NOT the thrown-error path — refresh()'s try/catch never fires, so
		// only a degraded check inside the 200-response branch can catch it.
		api.notifications.get.mockResolvedValue({ notifications: [], degraded: true, user: "a@x.com" });
		const store = useNotificationStore();
		await store.refresh();
		expect(JSON.parse(localStorage.getItem("fac_notif_seen:a@x.com"))).toEqual(["gone-1", "n1"]);
		expect(JSON.parse(localStorage.getItem("fac_notif_dismissed:a@x.com"))).toEqual(["gone-2", "n1"]);
	});

	it("still prunes once a healthy (non-degraded) response arrives", async () => {
		localStorage.setItem("fac_notif_seen:a@x.com", JSON.stringify(["gone-1", "n1"]));
		api.notifications.get.mockResolvedValue({ notifications: [N()], degraded: false, user: "a@x.com" });
		const store = useNotificationStore();
		await store.refresh();
		expect(JSON.parse(localStorage.getItem("fac_notif_seen:a@x.com"))).toEqual(["n1"]);
	});
});
