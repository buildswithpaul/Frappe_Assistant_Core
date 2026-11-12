import { mount } from "@vue/test-utils";
import { describe, it, expect, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import MessageBubble from "../MessageBubble.vue";
import ChatInterface from "../ChatInterface.vue";
import { useChatStore } from "@/stores/chatStore";

function bubble(message, isLatest = true) {
	return mount(MessageBubble, {
		props: { message, isLatest },
		global: { stubs: { MessageBlockRenderer: true, FacoRobot: true } },
	});
}

describe("MessageBubble turn credit limit", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
	});

	it("shows the credit-limit notice with Continue after turn_budget_reached", () => {
		const store = useChatStore();
		store.messages.push({ role: "assistant", content: "Part one", blocks: [], isStreaming: true });
		// AR emits this routing notice when the turn's credit budget stops it.
		store.handleRoutingNotice({ code: "turn_budget_reached", stop_reason: "limit_credits" });

		const wrapper = bubble(store.messages.at(-1));
		const notice = wrapper.find(".budget-notice");
		expect(notice.exists()).toBe(true);
		expect(notice.text()).toContain("This turn reached its credit limit.");
		expect(notice.find(".continue-btn").exists()).toBe(true);
	});

	it("carries stop_reason from the notice onto the message", () => {
		const store = useChatStore();
		store.messages.push({ role: "assistant", content: "Part one", blocks: [], isStreaming: true });
		// AR adds stop_reason to the turn_budget_reached routing notice for every limit stop.
		store.handleRoutingNotice({ code: "turn_budget_reached", stop_reason: "limit_turns" });
		expect(store.messages.at(-1).budgetStopReason).toBe("limit_turns");
	});

	it.each([
		["limit_credits", "This turn reached its credit limit."],
		["limit_turns", "This answer reached its step limit."],
		["limit_total_tokens", "This answer reached its length limit."],
		["limit_output_tokens", "This answer reached its length limit."],
		[undefined, "This answer was stopped at a limit."],
		["something_new", "This answer was stopped at a limit."],
	])("words the notice for stop_reason %s and keeps Continue", (reason, text) => {
		// The store sets budgetStopReason from the AR notice's stop_reason; a missing one stays undefined.
		const wrapper = bubble({
			role: "assistant",
			content: "Part one",
			blocks: [],
			budgetReached: true,
			budgetStopReason: reason,
		});
		const notice = wrapper.find(".budget-notice");
		expect(notice.text()).toContain(text);
		expect(notice.find(".continue-btn").exists()).toBe(true);
	});

	it("Continue emits continue-turn", async () => {
		const wrapper = bubble({ role: "assistant", content: "Part one", blocks: [], budgetReached: true });
		await wrapper.find(".budget-notice .continue-btn").trigger("click");
		expect(wrapper.emitted("continue-turn")).toHaveLength(1);
	});

	it("Continue reaches the view through the conversation", async () => {
		const wrapper = mount(ChatInterface, {
			props: { messages: [{ role: "assistant", content: "Part one", blocks: [], budgetReached: true }] },
			global: { stubs: { MessageBlockRenderer: true, FacoRobot: true } },
		});
		await wrapper.find(".budget-notice .continue-btn").trigger("click");
		expect(wrapper.emitted("continue-turn")).toHaveLength(1);
	});

	it("offers Continue only on the latest message", () => {
		const wrapper = bubble({ role: "assistant", content: "Part one", blocks: [], budgetReached: true }, false);
		expect(wrapper.find(".budget-notice").exists()).toBe(true);
		expect(wrapper.find(".budget-notice .continue-btn").exists()).toBe(false);
	});

	it("leaves other routing notices off the bubble", () => {
		const store = useChatStore();
		store.messages.push({ role: "assistant", content: "", blocks: [], isStreaming: true });
		store.handleRoutingNotice({ code: "downgraded_for_credits" });
		expect(store.messages.at(-1).budgetReached).toBeUndefined();
	});
});
