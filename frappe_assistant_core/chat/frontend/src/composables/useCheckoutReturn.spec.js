import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { effectScope, ref } from "vue";

vi.mock("@/api/client", () => ({
	api: { billing: { verifyCheckoutReturn: vi.fn() } },
}));

const toast = {
	showToast: vi.fn(() => 7),
	showSuccess: vi.fn(),
	showError: vi.fn(),
	dismiss: vi.fn(),
};
vi.mock("@/composables/useToast", () => ({ useToast: () => toast }));

/** Records what this tab posts, and lets a test play another tab's message. */
class FakeChannel {
	static instances = [];
	constructor(name) {
		this.name = name;
		this.posted = [];
		this.listeners = new Set();
		FakeChannel.instances.push(this);
	}
	postMessage(data) {
		this.posted.push(data);
	}
	addEventListener(_type, fn) {
		this.listeners.add(fn);
	}
	removeEventListener(_type, fn) {
		this.listeners.delete(fn);
	}
	deliver(data) {
		this.listeners.forEach((fn) => fn({ data }));
	}
}

let api;
let parseCheckoutReturn;
let useCheckoutReturn;
let billingReloadTick;

function harness(query, { isAdmin = true } = {}) {
	const current = ref({ path: "/settings/billing", query: { ...query } });
	const router = {
		currentRoute: current,
		isReady: vi.fn(() => Promise.resolve()),
		replace: vi.fn((to) => {
			current.value = { ...current.value, ...to };
			return Promise.resolve();
		}),
	};
	const userStore = { isAdmin, loadQuota: vi.fn(() => Promise.resolve()) };
	const scope = effectScope();
	const checkout = scope.run(() =>
		useCheckoutReturn({ router, userStore, pollIntervalMs: 2000, timeoutMs: 30000 }),
	);
	return { router, userStore, scope, checkout, current };
}

beforeEach(async () => {
	vi.resetModules();
	vi.useFakeTimers();
	FakeChannel.instances = [];
	vi.stubGlobal("BroadcastChannel", FakeChannel);
	Object.values(toast).forEach((fn) => fn.mockClear());
	({ api } = await import("@/api/client"));
	api.billing.verifyCheckoutReturn.mockReset();
	({ parseCheckoutReturn, useCheckoutReturn } = await import("./useCheckoutReturn.js"));
	({ billingReloadTick } = await import("./_billing/billingRefresh.js"));
});

afterEach(() => {
	vi.useRealTimers();
	vi.unstubAllGlobals();
});

describe("parseCheckoutReturn", () => {
	it("reads the session and result the checkout page sent back", () => {
		expect(parseCheckoutReturn({ fac_checkout: "CHK-1", result: "processing" })).toEqual({
			session: "CHK-1",
			result: "processing",
		});
	});

	it("assumes success when a session comes back without a result", () => {
		expect(parseCheckoutReturn({ fac_checkout: "CHK-1" }).result).toBe("success");
	});

	it("ignores a result it does not recognise", () => {
		expect(parseCheckoutReturn({ fac_checkout: "CHK-1", result: "bogus" }).result).toBe(
			"success",
		);
	});

	it("maps the legacy markers", () => {
		expect(parseCheckoutReturn({ success: "true" })).toEqual({ session: null, result: "success" });
		expect(parseCheckoutReturn({ success: "false" }).result).toBe("cancelled");
		expect(parseCheckoutReturn({ checkout: "success", session_id: "cs_1" }).result).toBe(
			"success",
		);
		expect(parseCheckoutReturn({ checkout: "cancelled" }).result).toBe("cancelled");
	});

	it("is null for an ordinary page load", () => {
		expect(parseCheckoutReturn({ tab: "plans" })).toBeNull();
		expect(parseCheckoutReturn({})).toBeNull();
	});
});

describe("useCheckoutReturn", () => {
	it("does nothing on an ordinary page load", async () => {
		const { checkout, router, userStore } = harness({ tab: "plans" });

		await checkout.run();

		expect(api.billing.verifyCheckoutReturn).not.toHaveBeenCalled();
		expect(userStore.loadQuota).not.toHaveBeenCalled();
		expect(router.replace).not.toHaveBeenCalled();
	});

	it("polls until the purchase lands, then refreshes everything once", async () => {
		api.billing.verifyCheckoutReturn
			.mockResolvedValueOnce({ done: false, outcome: "processing" })
			.mockResolvedValueOnce({ done: true, outcome: "applied" });
		const { checkout, userStore, current } = harness({
			fac_checkout: "CHK-1",
			result: "success",
			tab: "plans",
		});
		const tickBefore = billingReloadTick.value;

		const done = checkout.run();
		await vi.advanceTimersByTimeAsync(2000);
		await done;

		expect(api.billing.verifyCheckoutReturn).toHaveBeenCalledTimes(2);
		expect(api.billing.verifyCheckoutReturn).toHaveBeenCalledWith("CHK-1");
		expect(userStore.loadQuota).toHaveBeenCalledTimes(1);
		expect(billingReloadTick.value).toBe(tickBefore + 1);
		expect(checkout.state.value).toBe("applied");
		expect(toast.showToast).toHaveBeenCalledWith("Confirming your payment…", "info", 0);
		expect(toast.dismiss).toHaveBeenCalledWith(7);
		expect(toast.showSuccess).toHaveBeenCalled();
		// Only the checkout markers go; the page's own query stays.
		expect(current.value.query).toEqual({ tab: "plans" });
	});

	it("tells the other tabs the plan changed", async () => {
		api.billing.verifyCheckoutReturn.mockResolvedValue({ done: true, outcome: "applied" });
		const { checkout } = harness({ fac_checkout: "CHK-1", result: "success" });

		await checkout.run();

		const channel = FakeChannel.instances.find((c) => c.name === "fac-billing");
		expect(channel.posted).toEqual([{ type: "billing-updated" }]);
	});

	it("stops polling after the time limit and says the plan will follow", async () => {
		api.billing.verifyCheckoutReturn.mockResolvedValue({ done: false, outcome: "processing" });
		const { checkout, userStore, current } = harness({
			fac_checkout: "CHK-1",
			result: "processing",
		});

		const done = checkout.run();
		await vi.advanceTimersByTimeAsync(60000);
		await done;

		// t = 0, 2, …, 30s — and not one call after.
		expect(api.billing.verifyCheckoutReturn).toHaveBeenCalledTimes(16);
		expect(checkout.state.value).toBe("processing");
		expect(toast.showToast).toHaveBeenCalledWith(
			"Payment received — your plan will update shortly.",
			"info",
			expect.any(Number),
		);
		expect(userStore.loadQuota).toHaveBeenCalledTimes(1);
		expect(current.value.query).toEqual({});
	});

	it("keeps polling through a failed request", async () => {
		api.billing.verifyCheckoutReturn
			.mockRejectedValueOnce(new Error("network"))
			.mockResolvedValueOnce({ done: true, outcome: "applied" });
		const { checkout } = harness({ fac_checkout: "CHK-1", result: "success" });

		const done = checkout.run();
		await vi.advanceTimersByTimeAsync(2000);
		await done;

		expect(checkout.state.value).toBe("applied");
	});

	it("reports a cancelled checkout without polling for it", async () => {
		const { checkout, userStore, current } = harness({
			fac_checkout: "CHK-1",
			result: "cancelled",
		});

		await checkout.run();

		expect(api.billing.verifyCheckoutReturn).not.toHaveBeenCalled();
		expect(userStore.loadQuota).not.toHaveBeenCalled();
		expect(checkout.state.value).toBe("cancelled");
		expect(toast.showToast).toHaveBeenCalledWith(
			"Checkout cancelled. No changes were made.",
			"info",
			expect.any(Number),
		);
		expect(current.value.query).toEqual({});
	});

	it("reports a failed payment as an error", async () => {
		const { checkout } = harness({ fac_checkout: "CHK-1", result: "failed" });

		await checkout.run();

		expect(checkout.state.value).toBe("failed");
		expect(toast.showError).toHaveBeenCalledWith(
			"The payment didn't go through. No changes were made to your plan.",
		);
	});

	it("reports a checkout the runtime says failed, even after a success redirect", async () => {
		api.billing.verifyCheckoutReturn.mockResolvedValue({ done: true, outcome: "failed" });
		const { checkout } = harness({ fac_checkout: "CHK-1", result: "success" });

		await checkout.run();

		expect(checkout.state.value).toBe("failed");
		expect(toast.showError).toHaveBeenCalled();
	});

	it("refreshes without polling for a legacy return that names no session", async () => {
		const { checkout, userStore, current } = harness({
			checkout: "success",
			session_id: "cs_1",
		});

		await checkout.run();

		expect(api.billing.verifyCheckoutReturn).not.toHaveBeenCalled();
		expect(userStore.loadQuota).toHaveBeenCalledTimes(1);
		expect(current.value.query).toEqual({});
	});

	it("leaves the seat-return handler its own session id", async () => {
		api.billing.verifyCheckoutReturn.mockResolvedValue({ done: true, outcome: "applied" });
		const { checkout, current } = harness({
			fac_checkout: "CHK-1",
			result: "success",
			seat_purchase: "1",
			session_id: "cs_1",
		});

		await checkout.run();

		expect(current.value.query).toEqual({ seat_purchase: "1", session_id: "cs_1" });
	});

	it("does not ask a non-admin's session to verify a purchase", async () => {
		const { checkout, userStore } = harness(
			{ fac_checkout: "CHK-1", result: "success" },
			{ isAdmin: false },
		);

		await checkout.run();

		expect(api.billing.verifyCheckoutReturn).not.toHaveBeenCalled();
		expect(userStore.loadQuota).toHaveBeenCalledTimes(1);
	});

	it("refreshes when another tab finishes a purchase", () => {
		const { userStore } = harness({});
		const tickBefore = billingReloadTick.value;

		FakeChannel.instances[0].deliver({ type: "billing-updated" });

		expect(userStore.loadQuota).toHaveBeenCalledTimes(1);
		expect(billingReloadTick.value).toBe(tickBefore + 1);
	});

	it("stops listening and polling once its scope is disposed", async () => {
		api.billing.verifyCheckoutReturn.mockResolvedValue({ done: false, outcome: "processing" });
		const { checkout, scope, userStore } = harness({ fac_checkout: "CHK-1" });

		const done = checkout.run();
		await vi.advanceTimersByTimeAsync(0);
		scope.stop();
		await vi.advanceTimersByTimeAsync(60000);
		await done;

		expect(api.billing.verifyCheckoutReturn).toHaveBeenCalledTimes(1);
		FakeChannel.instances[0].deliver({ type: "billing-updated" });
		expect(userStore.loadQuota).not.toHaveBeenCalled();
	});
});
