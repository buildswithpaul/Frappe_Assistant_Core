import { mount } from "@vue/test-utils";
import { describe, it, expect } from "vitest";
import ConversationList from "@/components/analytics/ConversationList.vue";

const CONVERSATIONS = [
	{
		conversation_id: "s1",
		title: "List the 15 most recent Sales Orders",
		user_id: "Administrator",
		total_credits: 35,
		message_count: 2,
		last_message_at: "2026-08-18 07:17:57",
	},
];

const mountList = (props = {}) =>
	mount(ConversationList, { props: { conversations: CONVERSATIONS, isAdmin: true, ...props } });

/**
 * The page reports two credit figures from two stores: the summary card counts
 * every source (chat, suggestions, classification, web search), this list
 * counts chat alone. They are both right and they never match, so the section
 * has to say which one it is — otherwise the gap reads as a bug, which is how
 * it was first reported. Deliberately no figures: the non-chat spend has no
 * user or admin toggle, so quoting a gap nobody can act on invites "what am I
 * being charged for?" without answering it. Usage by Source, directly above,
 * already carries the breakdown.
 */
describe("ConversationList credit scope", () => {
	it("names the credit scope", () => {
		expect(mountList().text()).toMatch(/chat credits only/i);
	});

	it("points at the panel that accounts for the rest", () => {
		expect(mountList().text()).toMatch(/usage by source/i);
	});

	it("explains the scope even when nothing is listed", () => {
		// An empty list beside non-zero credits is the confusing case, not the
		// harmless one — the caption is what tells the reader the spend was
		// non-chat rather than missing.
		const wrapper = mountList({ conversations: [] });
		expect(wrapper.text()).toMatch(/chat credits only/i);
		expect(wrapper.text()).toContain("No conversation data available for this period");
	});

	it("quotes no credit figure that would read as a shortfall", () => {
		expect(mountList({ totalCredits: 53 }).find(".scope-note").text()).not.toMatch(/\d/);
	});

	it("still lists the conversations", () => {
		expect(mountList().text()).toContain("List the 15 most recent Sales Orders");
	});
});
