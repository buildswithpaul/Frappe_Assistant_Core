export async function hasPendingInterrupt(sessionId) {
	if (!sessionId) return false;
	try {
		const r = await window.frappe.call({
			method: "frappe_assistant_core.chat.api.chat.get_pending_interrupt",
			args: { session_id: sessionId },
			type: "GET",
		});
		return !!(r.message && r.message.pending && r.message.event);
	} catch {
		return false;
	}
}
