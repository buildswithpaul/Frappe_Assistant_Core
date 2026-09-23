import { mount } from "@vue/test-utils";
import { describe, it, expect } from "vitest";
import SummaryCards from "@/components/analytics/SummaryCards.vue";

// A real 7-day window: 53 credits over 11 API calls, spread across a single
// conversation. Requests count every source — chat, suggestions, classifier —
// so they are never the number of conversations.
const SUMMARY = { credits_consumed: 53, request_count: 11, active_users: 1 };

function avgCard(props = {}) {
	const wrapper = mount(SummaryCards, {
		props: { summary: SUMMARY, mode: "admin", conversationCount: 1, ...props },
		global: { stubs: { TrendBadge: true } },
	});
	const card = wrapper
		.findAll(".summary-card")
		.find((c) => /avg per chat/i.test(c.text()));
	return { wrapper, card };
}

/**
 * "Avg per Chat / credits per conversation" divided by `request_count` in admin
 * mode, so it reported credits per API call under a label promising credits per
 * conversation — 5 where the answer was 53. `conversationCount` was already
 * being passed in and ignored.
 */
describe("SummaryCards average per conversation", () => {
	it("divides by conversations, not API calls", () => {
		const { card } = avgCard();
		expect(card.text()).toContain("53");
		expect(card.text()).not.toContain("5 ");
	});

	it("averages over conversations in user mode too", () => {
		const { card } = avgCard({ mode: "user", conversationCount: 4 });
		expect(card.text()).toContain("13"); // 53 / 4
	});

	it("names which credits it is averaging", () => {
		// The numerator spans every source while the conversation list below
		// counts chat alone, so the card has to say which figure this is.
		expect(avgCard().card.text()).toMatch(/all sources/i);
	});

	it("shows a dash rather than a number when no conversations remain", () => {
		// The post-erase case: GDPR erase drops the conversations but keeps the
		// token-usage rows for audit, so credits outlive what they were spent on.
		const { card } = avgCard({ conversationCount: 0 });
		expect(card.text()).toContain("—");
	});

	it("still reports total requests from the AR counter", () => {
		const { wrapper } = avgCard();
		const requests = wrapper
			.findAll(".summary-card")
			.find((c) => /total requests/i.test(c.text()));
		expect(requests.text()).toContain("11");
	});
});
