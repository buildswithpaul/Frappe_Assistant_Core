import { describe, it, expect, beforeAll, beforeEach, afterEach, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import ConversationsList from "@/components/layout/ConversationsList.vue";

beforeAll(() => {
	window.__ = (s) => s;
});
beforeEach(() => {
	setActivePinia(createPinia());
	vi.useFakeTimers({ toFake: ["Date"] });
	vi.setSystemTime(new Date("2026-06-15T12:00:00"));
});
afterEach(() => vi.useRealTimers());

const labelsFor = (sessions) =>
	mount(ConversationsList, {
		props: { sessions },
		global: { stubs: { ChatRow: true, ArchivedConversations: true } },
	})
		.findAll(".date-label")
		.map((l) => l.text());

describe("ConversationsList date groups", () => {
	it("adds the year to an older group and keeps two years apart", () => {
		const year = 2026;
		const labels = labelsFor([
			{ session_id: "a", last_activity: `${year - 1}-03-05T10:00:00` },
			{ session_id: "b", last_activity: `${year - 2}-03-05T10:00:00` },
		]);
		expect(labels).toEqual([`Mar 5, ${year - 1}`, `Mar 5, ${year - 2}`]);
	});

	it("omits the year for the current year", () => {
		const [label] = labelsFor([{ session_id: "a", last_activity: "2026-05-16T10:00:00" }]);
		expect(label).toBe("May 16");
	});

	it("renders no new-chat control in the Recents header", () => {
		const w = mount(ConversationsList, {
			props: { sessions: [], showNewChat: true },
			global: { stubs: { ChatRow: true, ArchivedConversations: true } },
		});
		expect(w.find(".section-header button").exists()).toBe(false);
	});
});
