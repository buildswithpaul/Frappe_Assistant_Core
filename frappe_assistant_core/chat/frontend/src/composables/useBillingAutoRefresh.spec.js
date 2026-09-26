import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { defineComponent, h, nextTick } from "vue";
import { mount } from "@vue/test-utils";

import { useBillingAutoRefresh } from "./useBillingAutoRefresh.js";
import { requestBillingReload } from "./_billing/billingRefresh.js";

function setVisibility(state) {
	Object.defineProperty(document, "visibilityState", { value: state, configurable: true });
	document.dispatchEvent(new Event("visibilitychange"));
}

function mountWith(reload, options) {
	const Host = defineComponent({
		setup() {
			useBillingAutoRefresh(reload, options);
			return () => h("div");
		},
	});
	return mount(Host);
}

describe("useBillingAutoRefresh", () => {
	beforeEach(() => vi.useFakeTimers());
	afterEach(() => {
		vi.useRealTimers();
		setVisibility("visible");
	});

	it("reloads quietly when a checkout return asks it to", async () => {
		const reload = vi.fn();
		const wrapper = mountWith(reload);

		requestBillingReload();
		await nextTick();

		expect(reload).toHaveBeenCalledWith({ silent: true });
		wrapper.unmount();
	});

	it("reloads when the tab comes back into view", () => {
		const reload = vi.fn();
		const wrapper = mountWith(reload, { throttleMs: 30000 });

		vi.advanceTimersByTime(31000);
		setVisibility("visible");

		expect(reload).toHaveBeenCalledTimes(1);
		wrapper.unmount();
	});

	it("does not reload more than once per throttle window", () => {
		const reload = vi.fn();
		const wrapper = mountWith(reload, { throttleMs: 30000 });

		vi.advanceTimersByTime(31000);
		setVisibility("visible");
		vi.advanceTimersByTime(5000);
		setVisibility("visible");

		expect(reload).toHaveBeenCalledTimes(1);
		wrapper.unmount();
	});

	it("ignores the tab being hidden", () => {
		const reload = vi.fn();
		const wrapper = mountWith(reload, { throttleMs: 0 });

		setVisibility("hidden");

		expect(reload).not.toHaveBeenCalled();
		wrapper.unmount();
	});

	it("stops listening once the page is gone", () => {
		const reload = vi.fn();
		mountWith(reload, { throttleMs: 0 }).unmount();

		setVisibility("visible");

		expect(reload).not.toHaveBeenCalled();
	});
});
