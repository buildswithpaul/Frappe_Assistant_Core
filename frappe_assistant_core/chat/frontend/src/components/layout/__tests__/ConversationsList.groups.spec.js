import { describe, it, expect, beforeAll, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import ConversationsList from "@/components/layout/ConversationsList.vue";

beforeAll(() => {
	window.__ = (s) => s;
});
beforeEach(() => setActivePinia(createPinia()));

const labelsFor = (sessions) =>
	mount(ConversationsList, {
		props: { sessions },
		global: { stubs: { ChatRow: true, ArchivedConversations: true } },
	})
		.findAll(".date-label")
		.map((l) => l.text());

describe("ConversationsList date groups", () => {
	it("adds the year to an older group and keeps two years apart", () => {
		const year = new Date().getFullYear();
		const labels = labelsFor([
			{ session_id: "a", last_activity: `${year - 1}-03-05T10:00:00` },
			{ session_id: "b", last_activity: `${year - 2}-03-05T10:00:00` },
		]);
		expect(labels).toEqual([`Mar 5, ${year - 1}`, `Mar 5, ${year - 2}`]);
	});

	it("omits the year for the current year", () => {
		const d = new Date();
		d.setDate(d.getDate() - 30);
		const [label] = labelsFor([{ session_id: "a", last_activity: d.toISOString() }]);
		expect(label).not.toMatch(/\d{4}/);
	});
});
