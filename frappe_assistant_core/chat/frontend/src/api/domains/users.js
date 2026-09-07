import { baseCall, getCall } from "../_core";

// Admin-only user management. The per-user `user` domain (singular) lives
// in domains/user.js and handles current-user / preferences / MCP servers.
export const users = {
	list: (status = null, limit = 50, offset = 0) =>
		getCall("frappe_assistant_core.chat.api.list_users", {
			status,
			limit,
			offset,
		}),

	getLimitStatus: () =>
		getCall("frappe_assistant_core.chat.api.get_user_limit_status"),

	suspend: (userId) =>
		baseCall("frappe_assistant_core.chat.api.suspend_user", {
			user_id: userId,
		}),

	remove: (userId) =>
		baseCall("frappe_assistant_core.chat.api.deregister_user", {
			user_id: userId,
		}),

	addUser: (userId) =>
		baseCall("frappe_assistant_core.chat.api.add_user", {
			user_id: userId,
		}),

	getAvailableUsers: () =>
		getCall("frappe_assistant_core.chat.api.get_available_users"),

	setUserCreditLimit: (userId, limit) =>
		baseCall("frappe_assistant_core.chat.api.set_user_credit_limit", {
			user_id: userId,
			monthly_credit_limit: limit,
		}),

	getMyCreditStatus: () =>
		getCall("frappe_assistant_core.chat.api.get_my_credit_status"),

	// Team invites — invite an existing site user as a Pending member
	// (reserves a billed seat, auto-activates on first use, 7-day expiry).
	inviteUser: (userId, userRole = null) =>
		baseCall("frappe_assistant_core.chat.api.invite_user", {
			user_id: userId,
			user_role: userRole,
		}),

	revokeInvite: (userId) =>
		baseCall("frappe_assistant_core.chat.api.revoke_invite", {
			user_id: userId,
		}),

	resendInvite: (userId) =>
		baseCall("frappe_assistant_core.chat.api.resend_invite", {
			user_id: userId,
		}),

	listInvites: () =>
		getCall("frappe_assistant_core.chat.api.list_invites"),

	// Member-management activity log (member actions only; never GDPR rows).
	// Each entry's `details` is a JSON string the caller must parse.
	getMemberAuditLog: (limit = 100, offset = 0) =>
		getCall("frappe_assistant_core.chat.api.get_member_audit_log", {
			limit,
			offset,
		}),
};
