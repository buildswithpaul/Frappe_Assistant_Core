import { mount } from "@vue/test-utils";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { setActivePinia, createPinia } from "pinia";

vi.mock("@/api/client", () => ({
	api: {
		feedback: {
			rateAnswer: vi.fn().mockResolvedValue({ feedback_id: "f" }),
			withdrawAnswerRating: vi.fn().mockResolvedValue({ withdrawn: true }),
			answerRatings: vi.fn().mockResolvedValue({}),
		},
	},
}));

import { api } from "@/api/client";
import { useUserStore } from "@/stores/userStore";
import { useAnswerRatingStore } from "@/stores/answerRatingStore";
import MessageBubble from "../MessageBubble.vue";
import AnswerRating from "./AnswerRating.vue";

const answer = (over = {}) => ({
	role: "assistant",
	content: "done",
	message_id: "msg-0123456789abcdef",
	isStreaming: false,
	...over,
});

describe("AnswerRating", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		vi.clearAllMocks();
		// production: the capabilities endpoint passes through AR's feedback_v2 block.
		useUserStore().capabilities = { feedback_v2: true };
	});

	const mountBubble = (message = answer()) => mount(MessageBubble, { props: { message } });

	it("hides thumbs when feedback_v2 is absent", () => {
		useUserStore().capabilities = {};
		expect(mountBubble().findComponent(AnswerRating).exists()).toBe(false);
	});

	it("hides thumbs while streaming", () => {
		expect(mountBubble(answer({ isStreaming: true })).findComponent(AnswerRating).exists()).toBe(false);
	});

	it("hides thumbs without a message_id", () => {
		expect(mountBubble(answer({ message_id: null })).findComponent(AnswerRating).exists()).toBe(false);
	});

	it("shows thumbs on a finished answer", () => {
		expect(mountBubble().findComponent(AnswerRating).exists()).toBe(true);
	});

	it("thumbs up calls rate with Up and fills the thumb", async () => {
		const w = mount(AnswerRating, { props: { messageId: "m1" } });
		await w.find("[data-test=thumb-up]").trigger("click");
		expect(api.feedback.rateAnswer).toHaveBeenCalledWith(
			expect.objectContaining({ messageId: "m1", reaction: "Up" })
		);
		expect(w.find("[data-test=thumb-up]").classes()).toContain("is-active");
	});

	it("clicking the filled thumb up withdraws", async () => {
		useAnswerRatingStore().ratings = { m1: { reaction: "Up", reasons: [] } };
		const w = mount(AnswerRating, { props: { messageId: "m1" } });
		await w.find("[data-test=thumb-up]").trigger("click");
		expect(api.feedback.withdrawAnswerRating).toHaveBeenCalledWith("m1");
		expect(w.find("[data-test=thumb-up]").classes()).not.toContain("is-active");
	});

	it("thumbs down opens the popover and Send posts the chosen keys", async () => {
		const w = mount(AnswerRating, { props: { messageId: "m1" } });
		expect(w.find("[data-test=reasons]").exists()).toBe(false);
		await w.find("[data-test=thumb-down]").trigger("click");
		expect(w.text()).toContain("What went wrong?");
		await w.find("[data-reason=slow]").trigger("click");
		await w.find("[data-reason=credits]").trigger("click");
		await w.find("[data-test=comment]").setValue("meh");
		await w.find("[data-test=send]").trigger("click");
		expect(api.feedback.rateAnswer).toHaveBeenCalledWith({
			messageId: "m1",
			reaction: "Down",
			reasons: ["slow", "credits"],
			comment: "meh",
		});
		expect(w.find("[data-test=reasons]").exists()).toBe(false);
	});

	it("a failed rate reverts the thumb", async () => {
		api.feedback.rateAnswer.mockRejectedValueOnce(new Error("boom"));
		const w = mount(AnswerRating, { props: { messageId: "m1" } });
		await w.find("[data-test=thumb-up]").trigger("click");
		await vi.waitFor(() =>
			expect(w.find("[data-test=thumb-up]").classes()).not.toContain("is-active")
		);
	});
});
