import { getHost } from "../host/index.js";

export async function hasPendingInterrupt(sessionId) {
	if (!sessionId) return false;
	try {
		const r = await getHost().call(
			"frappe_assistant_core.chat.api.chat.get_pending_interrupt",
			{ session_id: sessionId },
			"GET"
		);
		return !!(r.message && r.message.pending && r.message.event);
	} catch {
		return false;
	}
}
