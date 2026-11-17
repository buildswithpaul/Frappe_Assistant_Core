import { describe, it, expect, beforeEach, vi } from "vitest";
import { setActivePinia, createPinia } from "pinia";

vi.mock("@/api/client", () => ({
	api: {
		feedback: {
			pulseState: vi.fn(),
			markPulseShown: vi.fn().mockResolvedValue({ ok: true }),
			dismissPulse: vi.fn().mockResolvedValue({ ok: true }),
			submitPulse: vi.fn(),
		},
	},
}));

import { api } from "@/api/client";
import { useUserStore } from "../userStore";
import { useTourStore } from "../tourStore";
import { useSpotlightStore } from "../spotlightStore";
import { useChatStore } from "../chatStore";
import { usePulseStore } from "../pulseStore";

describe("pulseStore", () => {
	let store;
	beforeEach(() => {
		setActivePinia(createPinia());
		vi.clearAllMocks();
		api.feedback.pulseState.mockResolvedValue({ due: true });
		// production: the capabilities endpoint passes through AR's feedback_v2 block.
		useUserStore().capabilities = { feedback_v2: true };
		store = usePulseStore();
	});

	it("no pulse without feedback_v2", async () => {
		useUserStore().capabilities = {};
		await store.maybeShow();
		expect(store.visible).toBe(false);
		expect(api.feedback.pulseState).not.toHaveBeenCalled();
	});

	it("no pulse after an errored turn", async () => {
		// production: handleStreamError sets chatStore's error code when a turn fails.
		useChatStore().errorCode = "MODEL_FAILED";
		await store.maybeShow();
		expect(store.visible).toBe(false);
	});

	it("no pulse while the tour is open", async () => {
		// production: tourStore.open() runs on first login or from Help.
		useTourStore().isOpen = true;
		await store.maybeShow();
		expect(store.visible).toBe(false);
	});

	it("no pulse while a spotlight is showing", async () => {
		// production: spotlightStore.evaluate() sets current for an announcement.
		useSpotlightStore().current = { id: "x" };
		await store.maybeShow();
		expect(store.visible).toBe(false);
	});

	it("not due means no card", async () => {
		api.feedback.pulseState.mockResolvedValue({ due: false });
		await store.maybeShow();
		expect(store.visible).toBe(false);
	});

	it("a failed pulse_state means not due", async () => {
		api.feedback.pulseState.mockRejectedValue(new Error("boom"));
		await store.maybeShow();
		expect(store.visible).toBe(false);
	});

	it("shows once per page session, marks shown, and asks the server once", async () => {
		await store.maybeShow();
		expect(store.visible).toBe(true);
		expect(api.feedback.markPulseShown).toHaveBeenCalledTimes(1);
		store.visible = false;
		await store.maybeShow();
		await store.maybeShow();
		expect(store.visible).toBe(false);
		expect(api.feedback.pulseState).toHaveBeenCalledTimes(1);
		expect(api.feedback.markPulseShown).toHaveBeenCalledTimes(1);
	});

	it("a not-due answer is cached for the page session", async () => {
		api.feedback.pulseState.mockResolvedValue({ due: false });
		await store.maybeShow();
		await store.maybeShow();
		expect(api.feedback.pulseState).toHaveBeenCalledTimes(1);
	});

	it("a blocked attempt does not spend the page session", async () => {
		useTourStore().isOpen = true;
		await store.maybeShow();
		useTourStore().isOpen = false;
		await store.maybeShow();
		expect(store.visible).toBe(true);
	});

	it("a failed mark-shown is ignored", async () => {
		api.feedback.markPulseShown.mockRejectedValue(new Error("boom"));
		await store.maybeShow();
		expect(store.visible).toBe(true);
	});

	it("dismiss hides and calls dismiss_pulse, ignoring failure", async () => {
		api.feedback.dismissPulse.mockRejectedValue(new Error("boom"));
		await store.maybeShow();
		await store.dismiss();
		expect(api.feedback.dismissPulse).toHaveBeenCalledTimes(1);
		expect(store.visible).toBe(false);
	});

	it("submit posts, thanks for 3 seconds, then hides", async () => {
		vi.useFakeTimers();
		api.feedback.submitPulse.mockResolvedValue({ feedback_id: "f" });
		await store.maybeShow();
		await store.submit({ rating: 4, comment: "ok", contactOk: true });
		expect(api.feedback.submitPulse).toHaveBeenCalledWith({ rating: 4, comment: "ok", contactOk: true });
		expect(store.thanked).toBe(true);
		expect(store.visible).toBe(true);
		vi.advanceTimersByTime(3000);
		expect(store.visible).toBe(false);
		vi.useRealTimers();
	});

	it("a failed submit keeps the card and reports failure", async () => {
		api.feedback.submitPulse.mockRejectedValue(new Error("boom"));
		await store.maybeShow();
		expect(await store.submit({ rating: 2 })).toBe(false);
		expect(store.visible).toBe(true);
		expect(store.thanked).toBe(false);
	});
});
