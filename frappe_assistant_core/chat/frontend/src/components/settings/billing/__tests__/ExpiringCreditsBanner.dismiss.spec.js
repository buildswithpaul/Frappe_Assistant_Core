import { mount, flushPromises } from "@vue/test-utils";
import { describe, it, expect, vi, beforeEach } from "vitest";

/**
 * Dismissing "expires in 28 days" must not silence "expires tomorrow".
 *
 * Dismissal was remembered per batch, forever, in localStorage. That was
 * survivable while the banner only appeared inside the last week. Widening
 * the window to 30 days turned one click into a month of silence on credits
 * the customer paid for — so the key now carries the urgency rung, mirroring
 * the mail ladder server-side.
 */

const getExpiringCredits = vi.fn();

vi.mock("@/api/client", () => ({
	api: { billing: { getExpiringCredits: (...a) => getExpiringCredits(...a) } },
}));
vi.mock("@/utils/logger", () => ({ logger: { warn: vi.fn() } }));

import ExpiringCreditsBanner from "../ExpiringCreditsBanner.vue";

const BATCH = {
	name: "AR-CRT-2026-00001",
	credits_remaining: 50000,
	source: "Prepaid Purchase",
	expires_at: "2027-09-11T00:00:00",
};

async function render(days_remaining) {
	getExpiringCredits.mockResolvedValue({ batches: [{ ...BATCH, days_remaining }] });
	const wrapper = mount(ExpiringCreditsBanner);
	await flushPromises();
	return wrapper;
}

beforeEach(() => {
	localStorage.clear();
	getExpiringCredits.mockReset();
});

describe("ExpiringCreditsBanner dismissal", () => {
	it("stays dismissed within the same rung", async () => {
		const wrapper = await render(28);
		await wrapper.find(".expiring-dismiss").trigger("click");
		expect(wrapper.findAll(".expiring-banner")).toHaveLength(0);

		const reopened = await render(25);
		expect(reopened.findAll(".expiring-banner")).toHaveLength(0);
	});

	it("comes back when the batch crosses into a nearer rung", async () => {
		const wrapper = await render(28);
		await wrapper.find(".expiring-dismiss").trigger("click");

		const inSevenDayRung = await render(5);
		expect(inSevenDayRung.findAll(".expiring-banner")).toHaveLength(1);
	});

	it("comes back again for the final warning", async () => {
		let wrapper = await render(28);
		await wrapper.find(".expiring-dismiss").trigger("click");
		wrapper = await render(5);
		await wrapper.find(".expiring-dismiss").trigger("click");

		const lastDay = await render(1);
		expect(lastDay.findAll(".expiring-banner")).toHaveLength(1);
		expect(lastDay.find(".expiring-banner").classes()).toContain("urgent");
	});
});
