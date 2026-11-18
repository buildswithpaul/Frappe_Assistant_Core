import { mount } from "@vue/test-utils";
import { nextTick } from "vue";
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

	it("thumbs down records Down at once and opens the popover", async () => {
		const w = mount(AnswerRating, { props: { messageId: "m1" } });
		expect(w.find("[data-test=reasons]").exists()).toBe(false);
		await w.find("[data-test=thumb-down]").trigger("click");
		expect(api.feedback.rateAnswer).toHaveBeenCalledWith({
			messageId: "m1",
			reaction: "Down",
			reasons: [],
			comment: null,
		});
		expect(w.find("[data-test=thumb-down]").classes()).toContain("is-active");
		expect(w.text()).toContain("What went wrong?");
	});

	it("Send re-rates the Down with the chosen keys and comment", async () => {
		const w = mount(AnswerRating, { props: { messageId: "m1" } });
		await w.find("[data-test=thumb-down]").trigger("click");
		await w.find("[data-reason=slow]").trigger("click");
		await w.find("[data-reason=credits]").trigger("click");
		await w.find("[data-test=comment]").setValue("meh");
		await w.find("[data-test=send]").trigger("click");
		await vi.waitFor(() => expect(api.feedback.rateAnswer).toHaveBeenCalledTimes(2));
		expect(api.feedback.rateAnswer).toHaveBeenLastCalledWith({
			messageId: "m1",
			reaction: "Down",
			reasons: ["slow", "credits"],
			comment: "meh",
		});
		expect(w.find("[data-test=reasons]").exists()).toBe(false);
		expect(w.find("[data-test=thumb-down]").classes()).toContain("is-active");
	});

	it("Send with nothing chosen adds no second call", async () => {
		const w = mount(AnswerRating, { props: { messageId: "m1" } });
		await w.find("[data-test=thumb-down]").trigger("click");
		await w.find("[data-test=send]").trigger("click");
		expect(api.feedback.rateAnswer).toHaveBeenCalledTimes(1);
		expect(w.find("[data-test=reasons]").exists()).toBe(false);
	});

	it("closing the popover without Send keeps the Down", async () => {
		const w = mount(AnswerRating, { props: { messageId: "m1" } });
		await w.find("[data-test=thumb-down]").trigger("click");
		await w.find("[data-test=reasons]").trigger("keydown", { key: "Escape" });
		expect(w.find("[data-test=reasons]").exists()).toBe(false);
		await vi.waitFor(() => expect(api.feedback.rateAnswer).toHaveBeenCalledTimes(1));
		expect(api.feedback.withdrawAnswerRating).not.toHaveBeenCalled();
		expect(w.find("[data-test=thumb-down]").classes()).toContain("is-active");
	});

	it("clicking the filled thumb down withdraws and closes the popover", async () => {
		const w = mount(AnswerRating, { props: { messageId: "m1" } });
		await w.find("[data-test=thumb-down]").trigger("click");
		await w.find("[data-test=thumb-down]").trigger("click");
		await vi.waitFor(() => expect(api.feedback.withdrawAnswerRating).toHaveBeenCalledWith("m1"));
		expect(w.find("[data-test=reasons]").exists()).toBe(false);
		expect(w.find("[data-test=thumb-down]").classes()).not.toContain("is-active");
	});

	it("tells the user what a rating is linked to, on both thumbs", () => {
		const w = mount(AnswerRating, { props: { messageId: "m1" } });
		for (const thumb of ["thumb-up", "thumb-down"]) {
			expect(w.find(`[data-test=${thumb}]`).attributes("title")).toContain(
				"usage record (model, time, credits), not to what you wrote"
			);
		}
	});

	it("caps the comment at 2000 characters", async () => {
		const w = mount(AnswerRating, { props: { messageId: "m1" } });
		await w.find("[data-test=thumb-down]").trigger("click");
		expect(w.find("[data-test=comment]").attributes("maxlength")).toBe("2000");
	});

	it("a failed rate reverts the thumb", async () => {
		api.feedback.rateAnswer.mockRejectedValueOnce(new Error("boom"));
		const w = mount(AnswerRating, { props: { messageId: "m1" } });
		await w.find("[data-test=thumb-up]").trigger("click");
		await vi.waitFor(() =>
			expect(w.find("[data-test=thumb-up]").classes()).not.toContain("is-active")
		);
	});

	describe("popover", () => {
		const openPopover = async () => {
			const w = mount(AnswerRating, { props: { messageId: "m1" }, attachTo: document.body });
			await w.find("[data-test=thumb-down]").trigger("click");
			await nextTick();
			return w;
		};

		it("moves focus in on open and back to the thumb on Escape", async () => {
			const w = await openPopover();
			expect(w.find("[data-test=thumb-down]").attributes("aria-expanded")).toBe("true");
			expect(w.find("[data-test=reasons]").element).toBe(document.activeElement);
			await w.find("[data-test=reasons]").trigger("keydown", { key: "Escape" });
			expect(w.find("[data-test=reasons]").exists()).toBe(false);
			expect(w.find("[data-test=thumb-down]").element).toBe(document.activeElement);
			w.unmount();
		});

		it("closes on an outside click", async () => {
			const w = await openPopover();
			document.body.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
			await nextTick();
			expect(w.find("[data-test=reasons]").exists()).toBe(false);
			w.unmount();
		});

		it("stays open on a click inside", async () => {
			const w = await openPopover();
			w.find("[data-test=comment]").element.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
			await nextTick();
			expect(w.find("[data-test=reasons]").exists()).toBe(true);
			w.unmount();
		});
	});
});
