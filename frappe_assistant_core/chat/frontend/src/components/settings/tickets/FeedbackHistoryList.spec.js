import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";

import FeedbackHistoryList from "@/components/settings/tickets/FeedbackHistoryList.vue";

const nullRatingItem = {
	name: "FB-1",
	rating: null,
	status: "Received",
	comment: "no rating given",
	category: "Product",
	submitted_at: "2026-08-01T00:00:00Z",
	escalated_ticket: null,
};

describe("FeedbackHistoryList rating rendering", () => {
	it("renders no .fb-rating node for a null rating (never zero stars)", () => {
		const w = mount(FeedbackHistoryList, { props: { items: [nullRatingItem] } });
		expect(w.find(".fb-rating").exists()).toBe(false);
		expect(w.find(".fb-status").text()).toBe("Received");
	});

	it("renders one star per point for a rated item", () => {
		const w = mount(FeedbackHistoryList, {
			props: { items: [{ ...nullRatingItem, rating: 3 }] },
		});
		expect(w.find(".fb-rating").findAll("span")).toHaveLength(3);
	});
});
