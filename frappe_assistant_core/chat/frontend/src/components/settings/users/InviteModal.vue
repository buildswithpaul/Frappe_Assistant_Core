<template>
	<Teleport to="body">
		<div v-if="open" class="modal-overlay" @click.self="$emit('close')">
			<div class="invite-modal">
				<div class="modal-header">
					<h3>Invite a teammate</h3>
					<button class="modal-close-btn" @click="$emit('close')">&times;</button>
				</div>

				<div class="modal-body">
					<!-- Role picker -->
					<label class="field-label" for="invite-role">Role</label>
					<select id="invite-role" v-model="selectedRole" class="role-select">
						<option value="Admin">Admin</option>
						<option value="Member">Member</option>
					</select>
					<p class="field-hint">
						{{
							selectedRole === "Admin"
								? "Admins can manage members, billing, and settings."
								: "Members can use the assistant but can't manage the team."
						}}
					</p>

					<!-- User search + selectable list -->
					<label class="field-label" for="invite-search">Who</label>
					<input
						id="invite-search"
						v-model="search"
						placeholder="Search site users..."
						class="user-search-input"
						ref="searchInput"
					/>

					<div v-if="loading" class="modal-loading-state">
						<svg class="spinner" viewBox="0 0 24 24">
							<circle
								cx="12"
								cy="12"
								r="10"
								stroke="currentColor"
								stroke-width="3"
								fill="none"
								opacity="0.25"
							/>
							<path
								d="M12 2a10 10 0 0 1 10 10"
								stroke="currentColor"
								stroke-width="3"
								fill="none"
								stroke-linecap="round"
							/>
						</svg>
						<span>Loading users...</span>
					</div>

					<div v-else class="available-users-list">
						<div
							v-for="user in filteredUsers"
							:key="user.user_id"
							class="available-user-item"
							:class="{ selected: selectedUser?.user_id === user.user_id }"
							@click="selectedUser = user"
						>
							<div class="available-user-info">
								<span class="available-user-name">{{ user.full_name }}</span>
								<span class="available-user-email">{{ user.user_id }}</span>
							</div>
							<svg
								v-if="selectedUser?.user_id === user.user_id"
								class="check-icon"
								width="16"
								height="16"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M5 13l4 4L19 7"
								/>
							</svg>
						</div>
						<div v-if="filteredUsers.length === 0" class="modal-empty-state">
							No available users found
						</div>
					</div>

					<!-- Seat-impact notice -->
					<div class="seat-notice" :class="{ charge: seatCharge }">
						<svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								:d="seatCharge
									? 'M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z'
									: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z'"
							/>
						</svg>
						<span>{{ seatNotice }}</span>
					</div>
				</div>

				<div class="modal-footer">
					<button class="btn-secondary" @click="$emit('close')">Cancel</button>
					<button
						class="btn-primary"
						:disabled="!selectedUser || loading"
						@click="sendInvite"
					>
						Send invitation
					</button>
				</div>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
import { computed, ref, watch, nextTick } from "vue";
import { seatChargeRequired } from "./memberHelpers";

const props = defineProps({
	open: { type: Boolean, required: true },
	availableUsers: { type: Array, default: () => [] },
	loading: { type: Boolean, default: false },
	// Seat status (from get_user_limit_status) — drives the seat-impact notice.
	userLimit: { type: Object, default: null },
});

const emit = defineEmits(["close", "invite"]);

const search = ref("");
const selectedRole = ref("Member");
const selectedUser = ref(null);
const searchInput = ref(null);

const filteredUsers = computed(() => {
	if (!search.value) return props.availableUsers;
	const q = search.value.toLowerCase();
	return props.availableUsers.filter(
		(u) =>
			(u.full_name || "").toLowerCase().includes(q) ||
			(u.user_id || "").toLowerCase().includes(q)
	);
});

// Whether inviting one more user crosses into paid-seat territory. Uses the
// shared seatChargeRequired predicate so the notice and useAddUserFlow's
// actual charge decision can never disagree: a prorated seat is billed when
// the team is already at/over its included seats AND the plan charges per user.
const seatCharge = computed(() => seatChargeRequired(props.userLimit));

const seatNotice = computed(() =>
	seatCharge.value
		? "This invite is over your included seats — a prorated seat will be charged when you send it."
		: "Within your plan — no extra charge."
);

// "Member" is the friendly label; AR stores it as user_role "User".
function sendInvite() {
	if (!selectedUser.value) return;
	emit("invite", {
		userId: selectedUser.value.user_id,
		userRole: selectedRole.value === "Member" ? "User" : "Admin",
	});
}

// Reset transient selection each time the modal opens, and focus search.
watch(
	() => props.open,
	(open) => {
		if (open) {
			search.value = "";
			selectedUser.value = null;
			selectedRole.value = "Member";
			nextTick(() => searchInput.value?.focus());
		}
	}
);
</script>

<style scoped>
.modal-overlay {
	position: fixed;
	inset: 0;
	background: rgba(0, 0, 0, 0.5);
	display: flex;
	align-items: center;
	justify-content: center;
	z-index: 1200;
	padding: 1rem;
}

.invite-modal {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	width: 100%;
	max-width: 460px;
	max-height: 85vh;
	display: flex;
	flex-direction: column;
	box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}

.modal-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 1rem 1.25rem;
	border-bottom: 1px solid var(--ql-border);
}

.modal-header h3 {
	font-size: 1rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0;
}

.modal-close-btn {
	background: none;
	border: none;
	font-size: 1.5rem;
	line-height: 1;
	color: var(--ql-text-muted);
	cursor: pointer;
	padding: 0.25rem;
	border-radius: 0.25rem;
	transition: color 0.15s ease;
}

.modal-close-btn:hover {
	color: var(--ql-text);
}

.modal-body {
	padding: 1rem 1.25rem;
	overflow-y: auto;
	flex: 1;
}

.field-label {
	display: block;
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-text-secondary);
	text-transform: uppercase;
	letter-spacing: 0.025em;
	margin-bottom: 0.375rem;
}

.field-hint {
	font-size: 0.7rem;
	color: var(--ql-text-muted);
	margin: 0.375rem 0 1rem;
}

.role-select,
.user-search-input {
	width: 100%;
	padding: 0.625rem 0.75rem;
	font-size: 0.875rem;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	outline: none;
	transition: border-color 0.15s ease;
}

.user-search-input {
	margin-bottom: 0.75rem;
}

.user-search-input::placeholder {
	color: var(--ql-text-muted);
}

.role-select:focus,
.user-search-input:focus {
	border-color: var(--ql-accent);
	box-shadow: 0 0 0 3px var(--ql-accent-soft);
}

.modal-loading-state {
	display: flex;
	align-items: center;
	justify-content: center;
	gap: 0.5rem;
	padding: 2rem 0;
	color: var(--ql-text-muted);
	font-size: 0.875rem;
}

.spinner {
	width: 1.25rem;
	height: 1.25rem;
	animation: spin 1s linear infinite;
}

@keyframes spin {
	from {
		transform: rotate(0deg);
	}
	to {
		transform: rotate(360deg);
	}
}

.available-users-list {
	display: flex;
	flex-direction: column;
	gap: 0.125rem;
	max-height: 240px;
	overflow-y: auto;
}

.available-user-item {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 0.625rem 0.75rem;
	border-radius: 0.375rem;
	cursor: pointer;
	border: 1px solid transparent;
	transition: background 0.15s ease, border-color 0.15s ease;
}

.available-user-item:hover {
	background: var(--ql-subtle);
}

.available-user-item.selected {
	background: var(--ql-accent-soft);
	border-color: var(--ql-accent);
}

.available-user-info {
	display: flex;
	flex-direction: column;
	gap: 0.125rem;
	min-width: 0;
}

.available-user-name {
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.available-user-email {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.check-icon {
	flex-shrink: 0;
	color: var(--ql-accent);
}

.modal-empty-state {
	padding: 2rem 0;
	text-align: center;
	font-size: 0.875rem;
	color: var(--ql-text-muted);
}

.seat-notice {
	display: flex;
	align-items: flex-start;
	gap: 0.5rem;
	margin-top: 1rem;
	padding: 0.625rem 0.75rem;
	border-radius: 0.375rem;
	font-size: 0.75rem;
	line-height: 1.4;
	background: var(--ql-subtle);
	color: var(--ql-text-secondary);
}

.seat-notice svg {
	flex-shrink: 0;
	margin-top: 1px;
}

.seat-notice.charge {
	background: rgba(234, 179, 8, 0.08);
	color: #ca8a04;
}

.modal-footer {
	display: flex;
	justify-content: flex-end;
	gap: 0.75rem;
	padding: 1rem 1.25rem;
	border-top: 1px solid var(--ql-border);
}

.btn-secondary {
	padding: 0.5rem 1rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
	background: transparent;
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.btn-secondary:hover {
	background: var(--ql-subtle);
}

.btn-primary {
	padding: 0.5rem 1rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: white;
	background: var(--ql-accent);
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.btn-primary:hover:not(:disabled) {
	background: var(--ql-accent-hover);
}

.btn-primary:disabled {
	opacity: 0.6;
	cursor: not-allowed;
}

@media (max-width: 640px) {
	.modal-footer {
		flex-direction: column;
	}

	.modal-footer .btn-secondary,
	.modal-footer .btn-primary {
		width: 100%;
		text-align: center;
	}
}
</style>
