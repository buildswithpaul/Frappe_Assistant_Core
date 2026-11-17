import { describe, it, expect, beforeEach, vi } from "vitest";
import { setActivePinia, createPinia } from "pinia";

vi.mock("@/api/client", () => ({
	api: {
		feedback: {
			rateAnswer: vi.fn(),
			withdrawAnswerRating: vi.fn(),
			answerRatings: vi.fn(),
		},
	},
}));

import { api } from "@/api/client";
import { useAnswerRatingStore } from "../answerRatingStore";
import { useUserStore } from "../userStore";

describe("answerRatingStore", () => {
	let store;
	beforeEach(() => {
		setActivePinia(createPinia());
		vi.clearAllMocks();
		// production: the capabilities endpoint passes through AR's feedback_v2 block.
		useUserStore().capabilities = { feedback_v2: true };
		store = useAnswerRatingStore();
	});

	it("load maps server ratings onto messages", async () => {
		api.feedback.answerRatings.mockResolvedValue({
			"msg-1": { reaction: "Down", reasons: ["slow"] },
		});
		await store.load("s1");
		expect(store.ratings["msg-1"]).toEqual({ reaction: "Down", reasons: ["slow"] });
	});

	it("load replaces the previous session's ratings", async () => {
		api.feedback.answerRatings.mockResolvedValueOnce({ a: { reaction: "Up", reasons: [] } });
		await store.load("s1");
		api.feedback.answerRatings.mockResolvedValueOnce({});
		await store.load("s2");
		expect(store.ratings).toEqual({});
	});

	it("load is skipped without feedback_v2", async () => {
		useUserStore().capabilities = {};
		await store.load("s1");
		expect(api.feedback.answerRatings).not.toHaveBeenCalled();
	});

	it("rate sets the state optimistically and keeps it on success", async () => {
		let resolve;
		api.feedback.rateAnswer.mockReturnValue(new Promise((r) => (resolve = r)));
		const p = store.rate("m1", "Up");
		expect(store.ratings.m1).toEqual({ reaction: "Up", reasons: [] });
		resolve({ feedback_id: "f1" });
		await p;
		expect(store.ratings.m1.reaction).toBe("Up");
	});

	it("a failed rate reverts the optimistic state", async () => {
		store.ratings = { m1: { reaction: "Up", reasons: [] } };
		api.feedback.rateAnswer.mockRejectedValue(new Error("boom"));
		await store.rate("m1", "Down", ["slow"]);
		expect(store.ratings.m1).toEqual({ reaction: "Up", reasons: [] });
	});

	it("a failed first rate removes the entry", async () => {
		api.feedback.rateAnswer.mockRejectedValue(new Error("boom"));
		await store.rate("m1", "Up");
		expect(store.ratings.m1).toBeUndefined();
	});

	it("a locked response restores the stored state from the server", async () => {
		store.ratings = { m1: { reaction: "Up", reasons: [] } };
		api.feedback.rateAnswer.mockResolvedValue({ feedback_id: "f", locked: true });
		api.feedback.answerRatings.mockResolvedValue({ m1: { reaction: "Up", reasons: [] } });
		await store.load("s1");
		await store.rate("m1", "Down", ["wrong"]);
		expect(store.ratings.m1).toEqual({ reaction: "Up", reasons: [] });
	});

	it("withdraw clears the entry, even when AR kept it", async () => {
		store.ratings = { m1: { reaction: "Up", reasons: [] } };
		api.feedback.withdrawAnswerRating.mockResolvedValue({ withdrawn: false });
		await store.withdraw("m1");
		expect(store.ratings.m1).toBeUndefined();
	});

	it("a failed withdraw restores the entry", async () => {
		store.ratings = { m1: { reaction: "Up", reasons: [] } };
		api.feedback.withdrawAnswerRating.mockRejectedValue(new Error("boom"));
		await store.withdraw("m1");
		expect(store.ratings.m1).toEqual({ reaction: "Up", reasons: [] });
	});
});
