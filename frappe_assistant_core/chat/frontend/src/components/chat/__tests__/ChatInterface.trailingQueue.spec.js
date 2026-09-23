import { mount } from "@vue/test-utils";
import { describe, it, expect, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import ChatInterface from "../ChatInterface.vue";

const streamingAssistant = {
	role: "assistant",
	message_id: "m1",
	isStreaming: true,
	content: "still typing",
	blocks: [{ type: "text", id: "b1", content: "still typing" }],
};

const queuedBubble = {
	role: "user",
	content: "later please",
	queued: true,
	_queueId: "q1",
};

describe("ChatInterface streaming indicator with a trailing queued bubble", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
	});

	it("keeps the streaming indicator on the assistant turn once a queued bubble is appended after it", () => {
		const wrapper = mount(ChatInterface, {
			props: {
				messages: [streamingAssistant, queuedBubble],
				isStreaming: true,
			},
		});
		// Regression guard: the streaming/latest flags used to be keyed off
		// "last item in the array", which broke the moment a queued bubble
		// trailed the live assistant turn.
		expect(wrapper.find(".streaming-indicator").exists()).toBe(true);
		expect(wrapper.find(".queued-chip").exists()).toBe(true);
	});
});
