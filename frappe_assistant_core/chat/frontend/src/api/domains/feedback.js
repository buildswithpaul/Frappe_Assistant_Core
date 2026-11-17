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

	pulseState: () => getCall("frappe_assistant_core.chat.api.support.pulse_state"),

	markPulseShown: () => baseCall("frappe_assistant_core.chat.api.support.mark_pulse_shown", {}),

	dismissPulse: () => baseCall("frappe_assistant_core.chat.api.support.dismiss_pulse", {}),

	submitPulse: ({ rating, comment = null, contactOk = false }) =>
		baseCall("frappe_assistant_core.chat.api.support.submit_pulse", {
			rating,
			comment: comment || null,
			contact_ok: contactOk,
		}),
};
