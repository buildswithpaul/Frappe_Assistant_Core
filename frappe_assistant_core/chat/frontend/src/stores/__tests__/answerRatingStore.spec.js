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

	it("a locked response restores the confirmed state and re-reads the server", async () => {
		api.feedback.answerRatings.mockResolvedValueOnce({ m1: { reaction: "Up", reasons: [] } });
		await store.load("s1");
		api.feedback.rateAnswer.mockResolvedValue({ feedback_id: "f", locked: true });
		// production: support triaged the rating, so AR may hold a state the click never saw.
		api.feedback.answerRatings.mockResolvedValueOnce({
			m1: { reaction: "Down", reasons: ["wrong"] },
		});
		await store.rate("m1", "Down", ["slow"]);
		expect(api.feedback.answerRatings).toHaveBeenCalledTimes(2);
		expect(store.ratings.m1).toEqual({ reaction: "Down", reasons: ["wrong"] });
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

	describe("overlapping calls", () => {
		const deferred = () => {
			let resolve, reject;
			const promise = new Promise((res, rej) => ((resolve = res), (reject = rej)));
			return { promise, resolve, reject };
		};

		it("sends calls for one message in click order", async () => {
			const up = deferred();
			api.feedback.rateAnswer.mockReturnValueOnce(up.promise).mockResolvedValueOnce({});
			const first = store.rate("m1", "Up");
			const second = store.rate("m1", "Down", ["slow"]);
			await Promise.resolve();
			expect(api.feedback.rateAnswer).toHaveBeenCalledTimes(1);
			expect(api.feedback.rateAnswer.mock.calls[0][0].reaction).toBe("Up");
			up.resolve({});
			await Promise.all([first, second]);
			expect(api.feedback.rateAnswer.mock.calls.map(([a]) => a.reaction)).toEqual(["Up", "Down"]);
		});

		it("keeps and sends the Down when the earlier Up fails", async () => {
			const up = deferred();
			api.feedback.rateAnswer.mockReturnValueOnce(up.promise).mockResolvedValueOnce({});
			const first = store.rate("m1", "Up");
			const second = store.rate("m1", "Down", ["slow"]);
			up.reject(new Error("boom"));
			await Promise.all([first, second]);
			expect(api.feedback.rateAnswer).toHaveBeenCalledTimes(2);
			expect(store.ratings.m1).toEqual({ reaction: "Down", reasons: ["slow"] });
		});

		it("reverts to the last confirmed state when the latest call fails", async () => {
			api.feedback.rateAnswer.mockResolvedValueOnce({}).mockRejectedValueOnce(new Error("boom"));
			await store.rate("m1", "Up");
			await store.rate("m1", "Down", ["slow"]);
			expect(store.ratings.m1).toEqual({ reaction: "Up", reasons: [] });
		});

		it("withdraw then a quick re-rate ends rated, in order", async () => {
			store.ratings = { m1: { reaction: "Up", reasons: [] } };
			const w = deferred();
			api.feedback.withdrawAnswerRating.mockReturnValueOnce(w.promise);
			api.feedback.rateAnswer.mockResolvedValueOnce({});
			const first = store.withdraw("m1");
			const second = store.rate("m1", "Down", ["slow"]);
			expect(api.feedback.rateAnswer).not.toHaveBeenCalled();
			w.resolve({ withdrawn: true });
			await Promise.all([first, second]);
			expect(store.ratings.m1).toEqual({ reaction: "Down", reasons: ["slow"] });
		});
	});

	describe("load", () => {
		const deferred = () => {
			let resolve, reject;
			const promise = new Promise((res, rej) => ((resolve = res), (reject = rej)));
			return { promise, resolve, reject };
		};

		it("ignores a stale response from the previous session", async () => {
			const a = deferred();
			api.feedback.answerRatings.mockReturnValueOnce(a.promise).mockResolvedValueOnce({
				b1: { reaction: "Up", reasons: [] },
			});
			const loadA = store.load("A");
			await store.load("B");
			a.resolve({ a1: { reaction: "Down", reasons: [] } });
			await loadA;
			expect(Object.keys(store.ratings)).toEqual(["b1"]);
		});

		it("a stale failure does not wipe the current session", async () => {
			const a = deferred();
			api.feedback.answerRatings.mockReturnValueOnce(a.promise).mockResolvedValueOnce({
				b1: { reaction: "Up", reasons: [] },
			});
			const loadA = store.load("A");
			await store.load("B");
			a.reject(new Error("late"));
			await loadA;
			expect(Object.keys(store.ratings)).toEqual(["b1"]);
		});

		it("keeps the optimistic state of a rating in flight", async () => {
			const load = deferred();
			api.feedback.answerRatings.mockReturnValueOnce(load.promise);
			const loading = store.load("s1");
			const rating = deferred();
			api.feedback.rateAnswer.mockReturnValueOnce(rating.promise);
			const rated = store.rate("m1", "Up");
			load.resolve({});
			await loading;
			expect(store.ratings.m1).toEqual({ reaction: "Up", reasons: [] });
			rating.resolve({});
			await rated;
		});

		it("reloads when feedback_v2 arrives after the session was set", async () => {
			useUserStore().capabilities = null;
			await store.load("s1");
			expect(api.feedback.answerRatings).not.toHaveBeenCalled();
			api.feedback.answerRatings.mockResolvedValue({ m1: { reaction: "Up", reasons: [] } });
			// production: capabilities load asynchronously at boot, after the session id is set.
			useUserStore().capabilities = { feedback_v2: true };
			await vi.waitFor(() => expect(store.ratings.m1?.reaction).toBe("Up"));
			expect(api.feedback.answerRatings).toHaveBeenCalledWith("s1");
		});
	});
});
