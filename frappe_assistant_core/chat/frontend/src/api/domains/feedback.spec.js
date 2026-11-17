import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("../_core", () => ({
	baseCall: vi.fn().mockResolvedValue({}),
	getCall: vi.fn().mockResolvedValue({}),
}));

import { baseCall, getCall } from "../_core";
import { feedback } from "./feedback";

const PREFIX = "frappe_assistant_core.chat.api.support.";

describe("feedback api domain", () => {
	beforeEach(() => vi.clearAllMocks());

	it("rateAnswer POSTs the reasons and comment", async () => {
		await feedback.rateAnswer({ messageId: "m1", reaction: "Down", reasons: ["slow"], comment: "x" });
		expect(baseCall).toHaveBeenCalledWith(`${PREFIX}rate_answer`, {
			message_id: "m1",
			reaction: "Down",
			reasons: ["slow"],
			comment: "x",
		});
	});

	it("rateAnswer normalises empty reasons and comment to null", async () => {
		await feedback.rateAnswer({ messageId: "m1", reaction: "Up", reasons: [], comment: "" });
		expect(baseCall).toHaveBeenCalledWith(`${PREFIX}rate_answer`, {
			message_id: "m1",
			reaction: "Up",
			reasons: null,
			comment: null,
		});
	});

	it("withdrawAnswerRating POSTs the message id", async () => {
		await feedback.withdrawAnswerRating("m1");
		expect(baseCall).toHaveBeenCalledWith(`${PREFIX}withdraw_answer_rating`, { message_id: "m1" });
	});

	it("answerRatings GETs by session id", async () => {
		await feedback.answerRatings("s1");
		expect(getCall).toHaveBeenCalledWith(`${PREFIX}answer_ratings`, { session_id: "s1" });
		expect(baseCall).not.toHaveBeenCalled();
	});
});
