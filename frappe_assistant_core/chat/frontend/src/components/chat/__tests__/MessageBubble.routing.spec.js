import { describe, it, expect, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import MessageBubble from "../MessageBubble.vue";
import { usePreferences } from "@/composables/usePreferences";

const RECEIPT = {
	v: 1,
	mode: "auto",
	incomplete: false,
	selected_model: "claude-sonnet-4-6",
	selected_tier: "Standard",
	fallback_from: null,
	classification: { complexity: "moderate", task_type: "general", source: "llm" },
	floor: { tier: "Standard", reasons: ["attachment_document"] },
	ceiling: { tier: "Premium", source: "plan", reasons: [] },
	bound_by: "floor",
	band: null,
	band_disclosed: "capacity_managed",
	pick_reason: "cost_weighted",
	thinking: { requested: false, applied: false },
	credits: { actual: 12 },
	cycles: 1,
	also_ran: [],
	notices: [],
	preference: null,
};

function bubble(message) {
	return mount(MessageBubble, {
		props: { message },
		global: { stubs: { MessageBlockRenderer: true, FacoRobot: true } },
	});
}

describe("the message footer stays quiet on an ordinary turn", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		const { preferences } = usePreferences();
		preferences.showRoutingChip = true;
	});

	it("shows NO chip when nothing surprising happened", () => {
		// The footer keeps the shape it had before auto mode. Everything the
		// receipt knows is one click away, and none of it is asserted at the
		// member unprompted.
		const w = bubble({
			role: "assistant",
			content: "hi",
			routing: RECEIPT,
			credits_used: 12,
		});
		expect(w.find(".message-routing-chip").exists()).toBe(false);
		expect(w.text()).not.toContain("Standard");
		expect(w.text()).not.toContain("Auto");
	});

	it("makes the credits figure the door to the panel", () => {
		const w = bubble({
			role: "assistant",
			content: "hi",
			routing: RECEIPT,
			credits_used: 12,
		});
		const door = w.find(".message-credits-door");
		expect(door.element.tagName).toBe("BUTTON");
		expect(door.attributes("aria-expanded")).toBe("false");
		expect(door.text()).toContain("12");
	});

	it("opens the panel from the credits door", async () => {
		const w = bubble({
			role: "assistant",
			content: "hi",
			routing: RECEIPT,
			credits_used: 12,
		});
		await w.find(".message-credits-door").trigger("click");
		expect(w.findComponent({ name: "RoutingPanel" }).exists()).toBe(true);
		expect(w.find(".message-credits-door").attributes("aria-expanded")).toBe("true");
	});

	it("falls back to a plain-word chip when the turn cost nothing", () => {
		// No figure to hang the panel on, so the chip carries the door — and
		// still names no model and no grade.
		const w = bubble({ role: "assistant", content: "hi", routing: RECEIPT, credits_used: 0 });
		const chip = w.find(".message-routing-chip");
		expect(chip.text()).toBe("How this ran");
		expect(w.find(".message-credits-door").exists()).toBe(false);
	});

	it("keeps raw model ids out of the door's tooltip", () => {
		// modelDisplayName returns null for an unknown id, so the fallback must
		// be a sentence — never `claude-sonnet-4-5-20250929`, which is a build
		// stamp and means nothing to someone reading a bill.
		const w = bubble({
			role: "assistant",
			content: "hi",
			routing: RECEIPT,
			credits_used: 12,
			model: "claude-sonnet-4-5-20250929",
		});
		const title = w.find(".message-credits-door").attributes("title");
		expect(title).not.toContain("claude-sonnet");
		expect(title).toContain("Click to see how it ran");
	});

	it("leaves credits alone when there is no receipt", () => {
		const w = bubble({ role: "assistant", content: "hi", credits_used: 4 });
		expect(w.find(".message-credits").exists()).toBe(true);
		expect(w.find(".message-credits-door").exists()).toBe(false);
		expect(w.find(".message-routing-chip").exists()).toBe(false);
	});

	it("NEVER renders on a user bubble, even when the row carries a receipt", () => {
		// get_session_messages returns the column for every row in the session
		// regardless of role — the !isUser containment is what stops it.
		const w = bubble({ role: "user", content: "hi", routing: RECEIPT });
		expect(w.find(".message-routing-chip").exists()).toBe(false);
		expect(w.find(".message-footer").exists()).toBe(false);
	});

	it("disappears entirely when the preference is off", () => {
		const { preferences } = usePreferences();
		preferences.showRoutingChip = false;
		const w = bubble({
			role: "assistant",
			content: "hi",
			routing: RECEIPT,
			credits_used: 12,
		});
		expect(w.find(".message-routing-chip").exists()).toBe(false);
		expect(w.find(".message-credits-door").exists()).toBe(false);
		expect(w.find(".message-credits").exists()).toBe(true);
	});
});

describe("the footer speaks up when the turn did not go as asked", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		const { preferences } = usePreferences();
		preferences.showRoutingChip = true;
	});

	const saver = { ...RECEIPT, notices: ["downgraded_for_credits"] };

	it("names what happened, in words, with no codename or grade", () => {
		const w = bubble({
			role: "assistant",
			content: "hi",
			routing: saver,
			credits_used: 12,
		});
		expect(w.find(".message-routing-chip").text()).toBe("Ran in saver mode");
	});

	it("keeps exactly one door — credits stays plain text beside the chip", () => {
		const w = bubble({
			role: "assistant",
			content: "hi",
			routing: saver,
			credits_used: 12,
		});
		expect(w.find(".message-credits-door").exists()).toBe(false);
		expect(w.find(".message-credits").exists()).toBe(true);
		expect(w.find(".message-credits").element.tagName).toBe("SPAN");
	});

	it("carries the L1 line as the chip's title", () => {
		const w = bubble({
			role: "assistant",
			content: "hi",
			routing: saver,
			credits_used: 12,
		});
		const title = w.find(".message-routing-chip").attributes("title");
		expect(title).toContain("attached a document");
		expect(title).not.toContain("Premium");
	});

	it("opens the panel on click and reports it in aria-expanded", async () => {
		const w = bubble({ role: "assistant", content: "hi", routing: saver });
		await w.find(".message-routing-chip").trigger("click");
		expect(w.find(".message-routing-chip").attributes("aria-expanded")).toBe("true");
		expect(w.findComponent({ name: "RoutingPanel" }).exists()).toBe(true);
	});
});
