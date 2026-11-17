import { baseCall, getCall } from "../_core";

export const feedback = {
	rateAnswer: ({ messageId, reaction, reasons = null, comment = null }) =>
		baseCall("frappe_assistant_core.chat.api.support.rate_answer", {
			message_id: messageId,
			reaction,
			reasons: reasons && reasons.length > 0 ? reasons : null,
			comment: comment || null,
		}),

	withdrawAnswerRating: (messageId) =>
		baseCall("frappe_assistant_core.chat.api.support.withdraw_answer_rating", {
			message_id: messageId,
		}),

	answerRatings: (sessionId) =>
		getCall("frappe_assistant_core.chat.api.support.answer_ratings", {
			session_id: sessionId,
		}),
};
