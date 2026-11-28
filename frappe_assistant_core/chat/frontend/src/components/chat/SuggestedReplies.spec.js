import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { describe, it, expect, beforeEach, vi } from "vitest";

vi.mock("frappe-ui", () => ({ call: vi.fn() }));

import MessageBubble from "@/components/chat/MessageBubble.vue";
import { useChatStore } from "@/stores/chatStore";

// A finished reply as the relay stores it, with the answers it offered.
const message = () => ({
	role: "assistant",
	message_id: "m1",
	content: "Draft created. Shall I submit it?",
	blocks: [
		{ type: "text", id: "t1", content: "Draft created. Shall I submit it?" },
		{ type: "suggested_replies", id: "s1", replies: ["Yes, submit it", "Stop here"] },
	],
});

const bubble = (props) =>
	mount(MessageBubble, {
		props: { message: message(), messageIndex: 1, ...props },
		global: { stubs: { AnswerRating: true, TurnCreditNotices: true, ReportFailedTurn: true } },
	});
const buttons = (wrapper) => wrapper.findAll(".suggested-reply");

describe("suggested replies under a reply", () => {
	beforeEach(() => setActivePinia(createPinia()));

	it("show under the latest finished reply, and a tap hands the answer up to be sent", async () => {
		const wrapper = bubble({ isLatest: true });

		expect(buttons(wrapper).map((b) => b.text())).toEqual(["Yes, submit it", "Stop here"]);
		await buttons(wrapper)[0].trigger("click");
		expect(wrapper.emitted("suggest")).toEqual([["Yes, submit it"]]);
	});

	it("do not show under an earlier reply or one still streaming", () => {
		expect(buttons(bubble({ isLatest: false }))).toHaveLength(0);
		expect(buttons(bubble({ isLatest: true, isStreaming: true }))).toHaveLength(0);
	});

	it("arrive on the reply the event names", () => {
		const store = useChatStore();
		store.messages = [{ role: "user", content: "post it" }, { role: "assistant", message_id: "m9", blocks: [] }];

		store.handleSuggestedReplies({ message_id: "m9", replies: ["Yes", "No"] });

		expect(store.messages[1].blocks).toEqual([expect.objectContaining({ type: "suggested_replies", replies: ["Yes", "No"] })]);
	});
});
