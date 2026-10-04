import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";

const getQuotaStatus = vi.fn();
const dismissApi = vi.fn();
vi.mock("@/api/client", () => ({
	api: {
		billing: { getQuotaStatus: (...a) => getQuotaStatus(...a) },
		notifications: { dismiss: (...a) => dismissApi(...a), get: vi.fn() },
	},
}));

import { useSpotlightStore } from "./spotlightStore";
import { useUserStore } from "./userStore";
import { useNotificationStore } from "./notificationStore";
import { useTourStore } from "./tourStore";

const today = () => {
	const d = new Date();
	return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

function setup({ admin = true, quota = null, notifications = [] } = {}) {
	setActivePinia(createPinia());
	const user = useUserStore();
	user.user = "owner@acme.com";
	user.isAdmin = admin;
	user.registrationStatus = "ready";
	// notificationStore.dismiss mutates items in place; copy so fixtures don't leak between tests.
	useNotificationStore().notifications = notifications.map((n) => ({ ...n }));
	getQuotaStatus.mockResolvedValue(quota);
	return useSpotlightStore();
}

const modalN = { id: "n1", display_style: "modal", title: "Agents", action_label: "Try", action_route: "/agents", dismissible: true };

beforeEach(() => {
	localStorage.clear();
	getQuotaStatus.mockReset();
	dismissApi.mockReset().mockResolvedValue({});
});

describe("spotlightStore", () => {
	it("quota moment wins over an announcement for admins", async () => {
		const s = setup({ quota: { percentage_used: 85, billing_cycle_start: "2026-09-24", plan: "Free" }, notifications: [modalN] });
		await s.evaluate();
		expect(s.current.kind).toBe("quota");
	});

	it("non-admins never get a quota moment", async () => {
		const s = setup({ admin: false, quota: { credits_exhausted: true }, notifications: [modalN] });
		await s.evaluate();
		expect(getQuotaStatus).not.toHaveBeenCalled();
		expect(s.current.kind).toBe("announcement");
	});

	it("quota moment shows once per cycle per threshold", async () => {
		const quota = { percentage_used: 85, billing_cycle_start: "2026-09-24" };
		let s = setup({ quota });
		await s.evaluate();
		s.dismiss();
		s = setup({ quota });
		await s.evaluate();
		expect(s.current).toBeNull();
		expect(localStorage.getItem("fac_quota_moment:owner@acme.com:2026-09-24:80")).toBe("1");
	});

	it("announcement obeys the daily cap", async () => {
		localStorage.setItem("fac_spotlight_last_shown:owner@acme.com", today());
		const s = setup({ admin: false, notifications: [modalN] });
		await s.evaluate();
		expect(s.current).toBeNull();
	});

	it("only one spotlight per page load", async () => {
		const s = setup({ admin: false, notifications: [modalN, { ...modalN, id: "n2" }] });
		await s.evaluate();
		s.dismiss();
		localStorage.clear();
		await s.evaluate();
		expect(s.current).toBeNull();
	});

	it("fetches quota status at most once per page load", async () => {
		const s = setup({ quota: { percentage_used: 10 } });
		await s.evaluate();
		await s.evaluate();
		await s.evaluate();
		expect(getQuotaStatus).toHaveBeenCalledTimes(1);
	});

	it("does nothing while the tour is open", async () => {
		const s = setup({ admin: false, notifications: [modalN] });
		useTourStore().isOpen = true;
		await s.evaluate();
		expect(s.current).toBeNull();
	});

	it("dismissing an announcement calls the dismiss endpoint", async () => {
		const s = setup({ admin: false, notifications: [modalN] });
		await s.evaluate();
		s.dismiss();
		expect(dismissApi).toHaveBeenCalledWith("n1");
	});

	it("primary routes in-app, or opens a safe url", async () => {
		const router = { push: vi.fn() };
		let s = setup({ admin: false, notifications: [modalN] });
		await s.evaluate();
		s.primary(router);
		expect(router.push).toHaveBeenCalledWith("/agents");

		const open = vi.spyOn(window, "open").mockImplementation(() => null);
		s = setup({ admin: false, notifications: [{ ...modalN, action_route: null, action_url: "javascript:alert(1)" }] });
		await s.evaluate();
		s.primary(router);
		expect(open).not.toHaveBeenCalled();
	});

	it("primary with no target just dismisses", async () => {
		const router = { push: vi.fn() };
		const open = vi.spyOn(window, "open").mockImplementation(() => null);
		const s = setup({ admin: false, notifications: [{ ...modalN, action_route: null, action_url: null }] });
		await s.evaluate();
		s.primary(router);
		expect(s.current).toBeNull();
		expect(router.push).not.toHaveBeenCalled();
		expect(open).not.toHaveBeenCalled();
	});

	it("quota_exhausted re-opens the 100 moment once per load", async () => {
		const s = setup({ quota: { credits_exhausted: true, billing_cycle_start: "2026-09-24" } });
		localStorage.setItem("fac_quota_moment:owner@acme.com:2026-09-24:100", "1");
		await s.onQuotaExhausted();
		expect(s.current.threshold).toBe(100);
		s.dismiss();
		await s.onQuotaExhausted();
		expect(s.current).toBeNull();
	});

	it("quota_exhausted forces the 100 moment even when the status is a fallback", async () => {
		const s = setup({ quota: { is_fallback: true, percentage_used: 0, is_unlimited: true } });
		await s.onQuotaExhausted();
		expect(s.current.threshold).toBe(100);
		expect(s.current.title).not.toContain("0%");
	});

	it("evaluate respects locally dismissed notifications", async () => {
		const s = setup({ admin: false, notifications: [modalN] });
		useNotificationStore().dismiss("n1");
		await s.evaluate();
		expect(s.current).toBeNull();
	});

	it("quota_exhausted is ignored for non-admins", async () => {
		const s = setup({ admin: false, quota: { credits_exhausted: true } });
		await s.onQuotaExhausted();
		expect(s.current).toBeNull();
	});
});
