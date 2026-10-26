import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount, flushPromises, enableAutoUnmount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { defineComponent, h } from "vue";

const getMyCreditStatus = vi.fn();
vi.mock("@/api/client", () => ({ api: { users: { getMyCreditStatus: (...a) => getMyCreditStatus(...a) } } }));

import { usePersonalLimitGate } from "./usePersonalLimitGate.js";

enableAutoUnmount(afterEach);

function mountGate() {
	let gate;
	const Probe = defineComponent({
		setup() {
			gate = usePersonalLimitGate();
			return () => h("i");
		},
	});
	mount(Probe);
	return () => gate;
}

describe("usePersonalLimitGate", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		getMyCreditStatus.mockReset();
	});

	it("holds when the user has used their whole personal limit", async () => {
		getMyCreditStatus.mockResolvedValue({ has_individual_limit: true, monthly_credit_limit: 10000, credits_used_this_month: 11234 });
		const gate = mountGate();
		await flushPromises();
		expect(gate().block.value).toEqual({ used: 11234, limit: 10000 });
	});

	it("does not hold under the limit, or with no personal limit", async () => {
		getMyCreditStatus.mockResolvedValue({ has_individual_limit: true, monthly_credit_limit: 10000, credits_used_this_month: 20 });
		const gate = mountGate();
		await flushPromises();
		expect(gate().block.value).toBeNull();

		getMyCreditStatus.mockResolvedValue({ has_individual_limit: false, monthly_credit_limit: 0, credits_used_this_month: 99999 });
		const gate2 = mountGate();
		await flushPromises();
		expect(gate2().block.value).toBeNull();
	});

	it("re-reads the limit when Desk regains focus, so a raised limit lifts the hold", async () => {
		getMyCreditStatus.mockResolvedValue({ has_individual_limit: true, monthly_credit_limit: 100, credits_used_this_month: 100 });
		const gate = mountGate();
		await flushPromises();
		expect(gate().block.value).not.toBeNull();

		getMyCreditStatus.mockResolvedValue({ has_individual_limit: false, monthly_credit_limit: 0, credits_used_this_month: 100 });
		window.dispatchEvent(new Event("focus"));
		await flushPromises();
		expect(getMyCreditStatus).toHaveBeenCalledTimes(2);
		expect(gate().block.value).toBeNull();
	});
});
