<template>
	<div class="members-tab">
		<!-- Toolbar: search + Role/Status filters + Invite -->
		<div class="members-toolbar">
			<div class="toolbar-search">
				<svg class="search-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
					/>
				</svg>
				<input
					v-model="search"
					type="text"
					class="search-input"
					placeholder="Search members..."
					aria-label="Search members"
				/>
			</div>

			<select v-model="roleFilter" class="toolbar-select" aria-label="Filter by role">
				<option value="">All roles</option>
				<option value="Owner">Owner</option>
				<option value="Admin">Admin</option>
				<option value="Member">Member</option>
			</select>

			<select v-model="statusFilter" class="toolbar-select" aria-label="Filter by status">
				<option value="">All statuses</option>
				<option value="Active">Active</option>
				<option value="Pending">Pending</option>
				<option value="Suspended">Suspended</option>
				<option value="Revoked">Revoked</option>
			</select>

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

		<!-- Empty: no members at all -->
		<div v-if="users.length === 0" class="empty-state">
			<div class="empty-icon">
				<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
					/>
				</svg>
			</div>
			<p>No members yet</p>
			<span class="empty-hint">Invite teammates to start building your team</span>
		</div>

		<!-- Empty: members exist but filters exclude them all -->
		<div v-else-if="filteredUsers.length === 0" class="empty-state">
			<p>No members match your filters</p>
			<button class="clear-filters-btn" @click="clearFilters">Clear filters</button>
		</div>

		<!-- Roster table -->
		<div v-else class="members-table-container">
			<table class="members-table">
				<thead>
					<tr>
						<th>Member</th>
						<th>Role</th>
						<th>Status</th>
						<th>Last Active</th>
						<th>Credits Used</th>
						<th>Limit</th>
						<th></th>
					</tr>
				</thead>
				<tbody>
					<MemberRow
						v-for="user in filteredUsers"
						:key="user.user_id"
						:user="user"
						:is-current="isCurrentUser(user.user_id)"
						:expanded="expandedUserId === user.user_id"
						:menu-open="openMenuId === user.user_id"
						:edit-credit-limit="editCreditLimit"
						:saving-limit="savingLimit"
						:action-loading="actionLoading"
						@open-member="$emit('open-member', $event)"
						@toggle-menu="$emit('toggle-menu', $event)"
						@toggle-expand="$emit('toggle-expand', $event)"
						@suspend="$emit('suspend', $event)"
						@remove="$emit('remove', $event)"
						@save-credit-limit="$emit('save-credit-limit', $event)"
						@update:editCreditLimit="$emit('update:editCreditLimit', $event)"
					/>
				</tbody>
			</table>

			<!-- Pagination -->
			<div v-if="pagination?.has_more" class="pagination">
				<button class="load-more-btn" @click="$emit('load-more')" :disabled="loadingMore">
					{{ loadingMore ? "Loading..." : "Load more" }}
				</button>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref, computed } from "vue";
import MemberRow from "./MemberRow.vue";

const props = defineProps({
	users: { type: Array, required: true },
	actionLoading: { type: Boolean, default: false },
	currentUser: { type: String, default: "" },
	// Expand / menu / credit-limit state stays owned by the parent so the
	// existing UsersSettings handlers wire through unchanged.
	expandedUserId: { type: String, default: null },
	editCreditLimit: { type: Number, default: 0 },
	savingLimit: { type: Boolean, default: false },
	openMenuId: { type: String, default: null },
	loadingMore: { type: Boolean, default: false },
	pagination: { type: Object, default: null },
});

defineEmits([
	"toggle-expand",
	"save-credit-limit",
	"toggle-menu",
	"suspend",
	"remove",
	"load-more",
	"update:editCreditLimit",
	"open-member",
	"invite",
]);

// Toolbar/filter state is local to the tab.
const search = ref("");
const roleFilter = ref("");
const statusFilter = ref("");

const filteredUsers = computed(() => {
	const q = search.value.trim().toLowerCase();
	return props.users.filter((user) => {
		if (q) {
			const haystack = `${user.user_id || ""} ${user.display_name || ""}`.toLowerCase();
			if (!haystack.includes(q)) return false;
		}
		if (roleFilter.value && (user.role || "Member") !== roleFilter.value) return false;
		if (statusFilter.value && (user.status || "Active") !== statusFilter.value) return false;
		return true;
	});
});

function clearFilters() {
	search.value = "";
	roleFilter.value = "";
	statusFilter.value = "";
}

function isCurrentUser(userId) {
	return userId === props.currentUser;
}
</script>

<style scoped>
.members-tab {
	margin-top: 1.25rem;
}

/* Toolbar */
.members-toolbar {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	margin-bottom: 1rem;
	flex-wrap: wrap;
}

.toolbar-search {
	position: relative;
	flex: 1;
	min-width: 180px;
}

.search-icon {
	position: absolute;
	left: 0.625rem;
	top: 50%;
	transform: translateY(-50%);
	width: 1rem;
	height: 1rem;
	color: var(--ql-text-muted);
	pointer-events: none;
}

.search-input {
	width: 100%;
	padding: 0.5rem 0.75rem 0.5rem 2.125rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	outline: none;
	transition: border-color 0.15s ease;
}

.search-input:focus {
	border-color: var(--ql-accent);
}

.toolbar-select {
	padding: 0.5rem 0.75rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	cursor: pointer;
	outline: none;
}

.toolbar-select:focus {
	border-color: var(--ql-accent);
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

/* Table shell */
.members-table-container {
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	overflow: visible;
}

.members-table {
	width: 100%;
	border-collapse: collapse;
	font-size: 0.875rem;
}

.members-table th {
	text-align: left;
	padding: 0.75rem 1rem;
	font-weight: 500;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.025em;
	background: var(--ql-surface);
	border-bottom: 1px solid var(--ql-border);
}

.members-table th:first-child {
	border-top-left-radius: 0.5rem;
}

.members-table th:last-child {
	border-top-right-radius: 0.5rem;
}

/* Pagination */
.pagination {
	padding: 0.75rem 1rem;
	text-align: center;
	border-top: 1px solid var(--ql-border);
}

.load-more-btn {
	padding: 0.5rem 1rem;
	font-size: 0.875rem;
	color: var(--ql-accent);
	background: transparent;
	border: 1px solid var(--ql-accent);
	border-radius: 0.375rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.load-more-btn:hover:not(:disabled) {
	background: var(--ql-accent-soft);
}

.load-more-btn:disabled {
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

.empty-hint {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.clear-filters-btn {
	padding: 0.375rem 0.875rem;
	font-size: 0.8125rem;
	color: var(--ql-accent);
	background: transparent;
	border: 1px solid var(--ql-accent);
	border-radius: 0.375rem;
	cursor: pointer;
}

.clear-filters-btn:hover {
	background: var(--ql-accent-soft);
}

/* Responsive */
@media (max-width: 720px) {
	.members-table th:nth-child(5),
	.members-table th:nth-child(6) {
		display: none;
	}
}
</style>
