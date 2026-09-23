<template>
	<div class="invites-tab">
		<!-- Header: count + Invite button -->
		<div class="invites-header">
			<span class="invites-count">
				{{ invites.length }}
				{{ invites.length === 1 ? "pending invitation" : "pending invitations" }}
			</span>
			<button class="btn-invite" @click="$emit('invite')">
				<svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M12 4v16m8-8H4"
					/>
				</svg>
				Invite
			</button>
		</div>

		<!-- Empty state -->
		<div v-if="invites.length === 0" class="empty-state">
			<div class="empty-icon">
				<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
					/>
				</svg>
			</div>
			<p>No pending invitations.</p>
			<button class="empty-cta" @click="$emit('invite')">Invite a teammate</button>
		</div>

		<!-- Pending invites list -->
		<ul v-else class="invites-list">
			<li v-for="invite in invites" :key="invite.user_id" class="invite-row">
				<div class="invite-main">
					<span class="invite-email">{{ invite.user_id }}</span>
					<span class="invite-meta">
						invited as
						<RoleBadge :role="displayRole(invite.user_role)" />
						<span class="meta-sep">·</span>
						{{ formatRelativeTime(invite.creation) }}
					</span>
				</div>

				<div class="invite-side">
					<span class="pending-badge">Pending</span>
					<span
						v-if="expiryHint(invite.modified)"
						class="expiry-hint"
						:class="{ warning: isExpiringSoon(invite.modified) }"
					>
						{{ expiryHint(invite.modified) }}
					</span>
				</div>

				<div class="invite-actions">
					<button
						class="action-link"
						:disabled="actionLoading"
						@click="$emit('resend', invite.user_id)"
					>
						Resend
					</button>
					<button
						class="action-link danger"
						:disabled="actionLoading"
						@click="$emit('revoke', invite.user_id)"
					>
						Revoke
					</button>
				</div>
			</li>
		</ul>
	</div>
</template>

<script setup>
import RoleBadge from "./RoleBadge.vue";
import { inviteExpiry, inviteExpiringSoon } from "./memberHelpers";
import { formatRelativeTime } from "@/composables/useFormatters";

defineProps({
	invites: { type: Array, default: () => [] },
	actionLoading: { type: Boolean, default: false },
});

defineEmits(["revoke", "resend", "invite"]);

// AR stores Member as user_role "User"; surface the friendlier label.
function displayRole(userRole) {
	return userRole === "User" ? "Member" : userRole || "Member";
}

function expiryHint(modified) {
	return inviteExpiry(modified);
}

function isExpiringSoon(modified) {
	return inviteExpiringSoon(modified);
}
</script>

<style scoped>
.invites-tab {
	margin-top: 1.25rem;
}

/* Header */
.invites-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 0.75rem;
	margin-bottom: 1rem;
	flex-wrap: wrap;
}

.invites-count {
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text-secondary);
}

.btn-invite {
	display: inline-flex;
	align-items: center;
	gap: 0.375rem;
	padding: 0.5rem 0.875rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: white;
	background: var(--ql-accent);
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
	transition: all 0.15s ease;
	white-space: nowrap;
}

.btn-invite:hover {
	background: var(--ql-accent-hover);
	transform: translateY(-1px);
	box-shadow: 0 2px 8px var(--ql-accent-soft);
}

/* List */
.invites-list {
	list-style: none;
	margin: 0;
	padding: 0;
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
}

.invite-row {
	display: flex;
	align-items: center;
	gap: 0.75rem;
	padding: 0.75rem 1rem;
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	flex-wrap: wrap;
}

.invite-main {
	display: flex;
	flex-direction: column;
	gap: 0.25rem;
	min-width: 0;
	flex: 1;
}

.invite-email {
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.invite-meta {
	display: inline-flex;
	align-items: center;
	gap: 0.375rem;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	flex-wrap: wrap;
}

.meta-sep {
	opacity: 0.6;
}

.invite-side {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	flex-wrap: wrap;
}

.pending-badge {
	display: inline-flex;
	padding: 1px 8px;
	border-radius: 9999px;
	font-size: 0.68rem;
	font-weight: 600;
	background: var(--ql-gold-soft);
	color: #8a6d12;
	white-space: nowrap;
}

[data-theme="dark"] .pending-badge {
	color: #e3c869;
}

.expiry-hint {
	font-size: 0.7rem;
	color: var(--ql-text-muted);
	white-space: nowrap;
}

.expiry-hint.warning {
	color: #ca8a04;
	font-weight: 500;
}

/* Actions */
.invite-actions {
	display: flex;
	align-items: center;
	gap: 0.75rem;
}

.action-link {
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-accent);
	background: none;
	border: none;
	padding: 0;
	cursor: pointer;
	transition: color 0.15s ease;
}

.action-link:hover:not(:disabled) {
	text-decoration: underline;
}

.action-link.danger {
	color: #dc2626;
}

.action-link:disabled {
	opacity: 0.5;
	cursor: not-allowed;
}

/* Empty state */
.empty-state {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 0.5rem;
	padding: 2rem 1rem;
	background: var(--ql-bg);
	border: 1px dashed var(--ql-border);
	border-radius: 0.5rem;
	text-align: center;
}

.empty-icon {
	width: 2.5rem;
	height: 2.5rem;
	color: var(--ql-text-muted);
}

.empty-state p {
	margin: 0;
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
}

.empty-cta {
	font-size: 0.8125rem;
	color: var(--ql-accent);
	background: transparent;
	border: 1px solid var(--ql-accent);
	border-radius: 0.375rem;
	padding: 0.375rem 0.875rem;
	cursor: pointer;
	transition: background 0.15s ease;
}

.empty-cta:hover {
	background: var(--ql-accent-soft);
}
</style>
