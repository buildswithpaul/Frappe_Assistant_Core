import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";

const push = vi.fn();
vi.mock("vue-router", () => ({ useRouter: () => ({ push }) }));
const getMyCreditStatus = vi.fn();
vi.mock("@/api/client", () => ({ api: { users: { getMyCreditStatus: (...a) => getMyCreditStatus(...a) } } }));

import CreditsTab from "./CreditsTab.vue";

const stubs = { PrepaidCreditsCard: { template: "<div data-test='card' />" }, UsageChart: true };

describe("CreditsTab", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		push.mockReset();
		getMyCreditStatus.mockReset();
	});

	it("says the personal limit is what stops the buyer, above the buy card", async () => {
		// The Desk widget's Buy credits opens this tab, and a blocked admin may arrive here first.
		getMyCreditStatus.mockResolvedValue({ has_individual_limit: true, monthly_credit_limit: 10000, credits_used_this_month: 11234 });
		const w = mount(CreditsTab, { global: { stubs } });
		await flushPromises();
		const html = w.html();
		expect(w.find('[data-test="personal-limit-notice"]').exists()).toBe(true);
		expect(html.indexOf("personal-limit-notice")).toBeLessThan(html.indexOf("data-test=\"card\""));
		await w.find('[data-test="open-users"]').trigger("click");
		expect(push).toHaveBeenCalledWith({ name: "settings-users" });
	});

	it("shows no notice under the limit", async () => {
		getMyCreditStatus.mockResolvedValue({ has_individual_limit: true, monthly_credit_limit: 10000, credits_used_this_month: 5 });
		const w = mount(CreditsTab, { global: { stubs } });
		await flushPromises();
		expect(w.find('[data-test="personal-limit-notice"]').exists()).toBe(false);
		expect(w.find('[data-test="card"]').exists()).toBe(true);
	});
});
