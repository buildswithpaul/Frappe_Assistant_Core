<template>
	<div class="users-settings">
		<!-- Loading State -->
		<div v-if="loading" class="loading-state">
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

		<!-- Error State -->
		<div v-else-if="error" class="error-state">
			<svg class="error-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
				/>
			</svg>
			<p>{{ error }}</p>
			<button class="retry-btn" @click="loadData">Retry</button>
		</div>

		<!-- Main Content -->
		<template v-else>
			<!-- User Limit Card -->
			<UserLimitCard
				:user-limit="userLimit"
				:min-users="userLimit?.min_users || 1"
				:price-per-user="userLimit?.price_per_user || 0"
				:credits-per-user="userLimit?.credits_per_user || 0"
				:currency="userLimit?.currency || 'USD'"
				:estimated-monthly-bill="userLimit?.estimated_monthly_bill || null"
				:credit-quota="userLimit?.credit_quota || 0"
			/>

			<VacantSeatsBanner
				:user-limit="userLimit"
				:releasing="releasing"
				@release="confirmReleaseSeat"
			/>

			<!-- Seat-cap upgrade prompt — appears only on bounded plans where
			     every seat is taken. Mirrors the language the blocked admin
			     sees in the connect-flow error so the resolution path is
			     consistent across the product. -->
			<SeatLimitUpgradeBanner
				v-if="atSeatLimit"
				:max-users="userLimit.max_users"
				@upgrade="goToBilling"
			/>

			<hr class="divider" />

			<!-- Tabs: Members / Invites / Activity -->
			<UsersTabs v-model="activeTab" :invite-count="pendingInvites.length" />

			<!-- Members tab -->
			<div v-if="activeTab === 'members'">
				<!-- Success/Error Messages -->
				<div v-if="successMessage" class="success-message">
					<svg
						class="message-icon"
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
					{{ successMessage }}
				</div>

				<div v-if="actionError" class="error-message">
					<svg
						class="message-icon"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M6 18L18 6M6 6l12 12"
						/>
					</svg>
					{{ actionError }}
				</div>

				<MembersTab
					:users="users"
					:action-loading="actionLoading"
					:current-user="currentUser"
					:expanded-user-id="expandedUserId"
					:edit-credit-limit="editCreditLimit"
					:saving-limit="savingLimit"
					:open-menu-id="openMenuId"
					:loading-more="loadingMore"
					:pagination="pagination"
					@toggle-expand="toggleExpand"
					@save-credit-limit="saveCreditLimit"
					@toggle-menu="toggleMenu"
					@suspend="handleSuspend"
					@remove="handleRemove"
					@load-more="loadMore"
					@update:edit-credit-limit="editCreditLimit = $event"
					@open-member="openMemberDrawer"
					@invite="openInviteModal"
				/>

				<!-- Suspended users note -->
				<div v-if="hasSuspendedUsers" class="suspended-note">
					<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
						/>
					</svg>
					<span>Suspended users will auto-reactivate when they reconnect</span>
				</div>
			</div>

			<!-- Invites tab -->
			<div v-else-if="activeTab === 'invites'">
				<div v-if="successMessage" class="success-message">
					<svg class="message-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M5 13l4 4L19 7"
						/>
					</svg>
					{{ successMessage }}
				</div>

				<div v-if="actionError" class="error-message">
					<svg class="message-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M6 18L18 6M6 6l12 12"
						/>
					</svg>
					{{ actionError }}
				</div>

				<InvitesTab
					:invites="pendingInvites"
					:action-loading="actionLoading"
					@invite="openInviteModal"
					@revoke="handleRevokeInvite"
					@resend="handleResendInvite"
				/>
			</div>

			<ActivityTab
				v-else-if="activeTab === 'activity'"
				:entries="auditEntries"
				:loading="activityLoading"
				:has-more="activityHasMore"
				@load-more="loadMoreActivity"
			/>
		</template>

		<!-- Member drill-down drawer -->
		<MemberDrawer
			:member="selectedMember"
			:open="drawerOpen"
			:current-user="currentUser"
			:action-loading="actionLoading"
			:saving-limit="savingLimit"
			@close="closeMemberDrawer"
			@suspend="suspendFromDrawer"
			@remove="removeFromDrawer"
			@save-credit-limit="saveCreditLimitFromDrawer"
		/>

		<!-- Invite Modal -->
		<InviteModal
			:open="showInviteModal"
			:available-users="availableUsers"
			:loading="loadingAvailableUsers"
			:user-limit="userLimit"
			@close="showInviteModal = false"
			@invite="handleInviteSend"
		/>

		<!-- Seat Purchase Confirmation Modal -->
		<SeatPurchaseModal
			:confirm-data="seatPurchaseConfirm"
			:processing="addingUser"
			@close="seatPurchaseConfirm = null"
			@confirm="confirmAddUser"
		/>

		<!-- Suspend / Remove confirmation -->
		<ConfirmModal
			:open="!!confirmModal"
			:title="confirmModal?.title || ''"
			:message="confirmModal?.message || ''"
			:warning="confirmModal?.warning || ''"
			:confirm-label="confirmModal?.confirmLabel || 'Confirm'"
			:processing-label="confirmModal?.processingLabel || 'Processing...'"
			:destructive="!!confirmModal?.destructive"
			:processing="actionLoading"
			@confirm="runConfirmedAction"
			@cancel="cancelConfirmedAction"
		/>
	</div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from "vue";
import { useRouter } from "vue-router";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";
import UserLimitCard from "./UserLimitCard.vue";
import UsersTabs from "./users/UsersTabs.vue";
import MembersTab from "./users/MembersTab.vue";
import InvitesTab from "./users/InvitesTab.vue";
import ActivityTab from "./users/ActivityTab.vue";
import MemberDrawer from "./users/MemberDrawer.vue";
import InviteModal from "./users/InviteModal.vue";
import SeatPurchaseModal from "./users/SeatPurchaseModal.vue";
import SeatLimitUpgradeBanner from "./users/SeatLimitUpgradeBanner.vue";
import VacantSeatsBanner from "./users/VacantSeatsBanner.vue";
import ConfirmModal from "@/components/common/ConfirmModal.vue";
import { useAddUserFlow } from "@/composables/useAddUserFlow";
import { useSeatRelease } from "@/composables/useSeatRelease";

const router = useRouter();

// State
const loading = ref(true);
const error = ref(null);
const activeTab = ref("members");
const pendingInvites = ref([]);

// Invite modal: reuses the add-user flow's availableUsers + seat-purchase
// branching, but commits via inviteUser instead of addUser.
const showInviteModal = ref(false);
const users = ref([]);
const userLimit = ref(null);
const pagination = ref(null);
const loadingMore = ref(false);
const actionLoading = ref(false);
const successMessage = ref("");
const actionError = ref("");
const openMenuId = ref(null);

// Expandable row state
const expandedUserId = ref(null);
const editCreditLimit = ref(0);
const savingLimit = ref(false);

// Member drill-down drawer state
const selectedMember = ref(null);
const drawerOpen = ref(false);

// Activity tab — member-management audit feed. Lazy-loaded the first time the
// tab is opened (see the activeTab watcher) so it never slows page load.
const AUDIT_PAGE_SIZE = 100;
const auditEntries = ref([]);
const activityLoading = ref(false);
const activityLoaded = ref(false);
// The endpoint returns only {entries:[...]} with no total/has_more signal, so
// infer "there may be more" from a full page. A short page means we have all.
const activityHasMore = ref(false);

// User-action confirm modal state. The same modal is reused for Suspend
// and Remove — `pendingAction` carries the executor to run on confirm.
const confirmModal = ref(null); // null | { title, message, warning, confirmLabel, destructive, run }

// Get current user from Frappe
const currentUser = window.frappe?.session?.user || "";

// Computed
const hasSuspendedUsers = computed(() => {
	return users.value.some((u) => u.status === "Suspended");
});

// Seat limit predicate — only true on bounded plans where every seat is
// occupied. Unlimited plans (`is_unlimited`) and plans with remaining
// capacity skip the upgrade banner.
const atSeatLimit = computed(() => {
	const limit = userLimit.value;
	if (!limit || limit.is_unlimited) return false;
	return (limit.active_users ?? 0) >= (limit.max_users ?? 0);
});

function goToBilling() {
	router.push("/settings/billing");
}

// Table interaction handlers

function toggleExpand(userId) {
	if (expandedUserId.value === userId) {
		expandedUserId.value = null;
		return;
	}
	expandedUserId.value = userId;
	const user = users.value.find((u) => u.user_id === userId);
	editCreditLimit.value = parseFloat(user?.monthly_credit_limit || 0) || 0;
}

async function saveCreditLimit(userId) {
	savingLimit.value = true;
	actionError.value = "";
	try {
		const result = await api.users.setUserCreditLimit(userId, editCreditLimit.value || 0);
		if (result?.success) {
			const user = users.value.find((u) => u.user_id === userId);
			if (user) user.monthly_credit_limit = editCreditLimit.value || 0;
			activityLoaded.value = false; // credit-limit change writes an audit event → refetch feed
			successMessage.value = `Credit limit updated for ${userId}`;
			setTimeout(() => {
				successMessage.value = "";
			}, 3000);
		} else {
			actionError.value = result?.error || "Failed to update credit limit";
		}
	} catch (e) {
		actionError.value = e.message || "Failed to update credit limit";
	} finally {
		savingLimit.value = false;
	}
}

function toggleMenu(userId) {
	openMenuId.value = openMenuId.value === userId ? null : userId;
}

function closeMenu() {
	openMenuId.value = null;
}

// Row click → member drill-down drawer.
function openMemberDrawer(user) {
	closeMenu();
	selectedMember.value = user;
	drawerOpen.value = true;
}

function closeMemberDrawer() {
	drawerOpen.value = false;
}

// Drawer Suspend/Remove route through the SAME ConfirmModal handlers the
// roster row uses. The confirm modal renders above the drawer (z-index 1200
// each, modal mounted later in DOM order so it stacks on top). On confirmed
// success the existing handlers refresh the roster; we also close the drawer
// so the stale member card doesn't linger over the fresh list.
function suspendFromDrawer(userId) {
	closeMemberDrawer();
	handleSuspend(userId);
}

function removeFromDrawer(userId) {
	closeMemberDrawer();
	handleRemove(userId);
}

// Drawer emits {userId, limit}; the existing saveCreditLimit reads from the
// shared editCreditLimit ref, so seed it before delegating.
function saveCreditLimitFromDrawer({ userId, limit }) {
	editCreditLimit.value = limit || 0;
	saveCreditLimit(userId);
}

// Data loading

async function loadData() {
	loading.value = true;
	error.value = null;

	try {
		const [limitResult, usersResult] = await Promise.all([
			api.users.getLimitStatus(),
			api.users.list(),
		]);

		if (limitResult.error) {
			throw new Error(limitResult.error);
		}
		if (usersResult.error) {
			throw new Error(usersResult.error);
		}

		userLimit.value = limitResult;
		users.value = usersResult.users || [];
		pagination.value = usersResult.pagination;

		// Invites are non-critical: a failure here shouldn't blank the page,
		// so load them separately (loadInvites swallows its own errors).
		await loadInvites();
	} catch (e) {
		error.value = e.message || "Failed to load user data";
	} finally {
		loading.value = false;
	}
}

// Pending-invite roster. Feeds the Invites tab and the tab-count badge.
async function loadInvites() {
	try {
		const result = await api.users.listInvites();
		pendingInvites.value = result.invites || [];
	} catch (e) {
		logger.error("Failed to load invites:", e);
	}
}

// Member-management audit feed. Non-critical — a failure leaves the tab empty
// rather than blanking the page (the error is swallowed).
async function loadActivity() {
	activityLoading.value = true;
	try {
		const result = await api.users.getMemberAuditLog(AUDIT_PAGE_SIZE, 0);
		const entries = result?.entries || [];
		auditEntries.value = entries;
		activityHasMore.value = entries.length >= AUDIT_PAGE_SIZE;
		activityLoaded.value = true;
	} catch (e) {
		logger.error("Failed to load member activity:", e);
	} finally {
		activityLoading.value = false;
	}
}

// Append the next audit page. Offset is the count we already hold.
async function loadMoreActivity() {
	if (activityLoading.value || !activityHasMore.value) return;
	activityLoading.value = true;
	try {
		const result = await api.users.getMemberAuditLog(
			AUDIT_PAGE_SIZE,
			auditEntries.value.length
		);
		const entries = result?.entries || [];
		auditEntries.value = [...auditEntries.value, ...entries];
		activityHasMore.value = entries.length >= AUDIT_PAGE_SIZE;
	} catch (e) {
		logger.error("Failed to load more member activity:", e);
	} finally {
		activityLoading.value = false;
	}
}

// Lazy-load the audit feed the first time the Activity tab is opened.
watch(activeTab, (tab) => {
	if (tab === "activity" && !activityLoaded.value) loadActivity();
});

async function loadMore() {
	if (loadingMore.value || !pagination.value?.has_more) return;

	loadingMore.value = true;
	try {
		const result = await api.users.list(null, 50, users.value.length);
		if (result.users) {
			users.value = [...users.value, ...result.users];
			pagination.value = result.pagination;
		}
	} catch (e) {
		actionError.value = "Failed to load more users";
		clearMessageAfterDelay("error");
	} finally {
		loadingMore.value = false;
	}
}

// User actions
//
// Suspend and Remove both go through ConfirmModal — kept consistent with
// other destructive flows in the app (no native browser confirm()).

function handleSuspend(userId) {
	closeMenu();
	confirmModal.value = {
		title: `Suspend ${userId}?`,
		message: "They won't be able to use FACO until they reconnect.",
		confirmLabel: "Suspend",
		processingLabel: "Suspending...",
		destructive: false,
		run: async () => {
			const result = await api.users.suspend(userId);
			if (result.error) throw new Error(result.error);
			successMessage.value = `${userId} has been suspended`;
			clearMessageAfterDelay("success");
			await refreshUsers();
		},
	};
}

function confirmReleaseSeat() {
	confirmModal.value = {
		title: "Release a seat?",
		message:
			"Your next bill drops by one seat. This cycle's credits are not " +
			"reduced, and there is no refund for the current period.",
		confirmLabel: "Release seat",
		processingLabel: "Releasing...",
		run: releaseSeat,
	};
}

function handleRemove(userId) {
	closeMenu();
	confirmModal.value = {
		title: `Permanently remove ${userId}?`,
		message: "Their MCP servers and OAuth tokens will be deleted.",
		warning:
			"Credits already paid for this billing cycle stay in the team pool. " +
			"Your next renewal will reflect the lower user count.",
		confirmLabel: "Remove user",
		processingLabel: "Removing...",
		destructive: true,
		run: async () => {
			const result = await api.users.remove(userId);
			if (result.error) throw new Error(result.error);
			successMessage.value = `${userId} has been removed`;
			clearMessageAfterDelay("success");
			await Promise.all([refreshUsers(), refreshLimit()]);
		},
	};
}

// Invite lifecycle ---------------------------------------------------------

// Open the invite modal, loading the site-users picker via the add-user
// flow's loader (it populates availableUsers/loadingAvailableUsers).
async function openInviteModal() {
	showInviteModal.value = true;
	await loadAvailableUsers();
}

// Modal emits { userId, userRole }. Route through startInvite so an invite
// over the included seats hits the SAME seat-purchase confirm an add would.
function handleInviteSend({ userId, userRole }) {
	showInviteModal.value = false;
	const picked = availableUsers.value.find((u) => u.user_id === userId) || {
		user_id: userId,
	};
	startInvite(picked, userRole);
}

async function handleRevokeInvite(userId) {
	actionLoading.value = true;
	actionError.value = "";
	successMessage.value = "";
	try {
		const result = await api.users.revokeInvite(userId);
		if (result?.error) throw new Error(result.error);
		successMessage.value = `Invitation to ${userId} revoked`;
		clearMessageAfterDelay("success");
		activityLoaded.value = false; // revoke writes an audit event → refetch feed
		await Promise.all([loadInvites(), refreshLimit()]);
	} catch (e) {
		actionError.value = e.message || "Failed to revoke invitation";
		clearMessageAfterDelay("error");
	} finally {
		actionLoading.value = false;
	}
}

async function handleResendInvite(userId) {
	actionLoading.value = true;
	actionError.value = "";
	successMessage.value = "";
	try {
		const result = await api.users.resendInvite(userId);
		if (result?.error) throw new Error(result.error);
		successMessage.value = `Invitation to ${userId} resent`;
		clearMessageAfterDelay("success");
		activityLoaded.value = false; // resend writes an audit event → refetch feed
		await loadInvites();
	} catch (e) {
		actionError.value = e.message || "Failed to resend invitation";
		clearMessageAfterDelay("error");
	} finally {
		actionLoading.value = false;
	}
}

async function runConfirmedAction() {
	if (!confirmModal.value) return;
	const action = confirmModal.value;
	actionLoading.value = true;
	actionError.value = "";
	successMessage.value = "";
	try {
		await action.run();
	} catch (e) {
		actionError.value = e.message || "Action failed";
		clearMessageAfterDelay("error");
	} finally {
		actionLoading.value = false;
		confirmModal.value = null;
	}
}

function cancelConfirmedAction() {
	if (actionLoading.value) return;
	confirmModal.value = null;
}

// Refresh helpers

async function refreshUsers() {
	// Any roster mutation that funnels through here (suspend, remove, invite
	// send) also writes a member-audit event, so invalidate the lazy-loaded
	// Activity feed — it refetches next time the tab is opened (the watcher
	// only fires on tab open, so this can't trigger a refetch loop).
	activityLoaded.value = false;
	try {
		const result = await api.users.list();
		if (result.users) {
			users.value = result.users;
			pagination.value = result.pagination;
		}
	} catch (e) {
		logger.error("Failed to refresh users:", e);
	}
}

async function refreshLimit() {
	try {
		const result = await api.users.getLimitStatus();
		if (!result.error) {
			userLimit.value = result;
		}
	} catch (e) {
		logger.error("Failed to refresh limit:", e);
	}
}

function clearMessageAfterDelay(type) {
	setTimeout(() => {
		if (type === "success") successMessage.value = "";
		else actionError.value = "";
	}, 5000);
}

// Click outside handler for dropdown menu
function handleClickOutside(event) {
	if (openMenuId.value && !event.target.closest(".actions-menu")) {
		closeMenu();
	}
}

// Add-user flow (open/select/confirm + gateway handoff + Stripe return).
// Composable owns the long imperative branching so the page reads in one screen.
const {
	availableUsers,
	loadingAvailableUsers,
	addingUser,
	seatPurchaseConfirm,
	loadAvailableUsers,
	confirmAddUser,
	handleStripeSeatReturn,
	startInvite,
} = useAddUserFlow({
	userLimit,
	actionError,
	successMessage,
	clearMessageAfterDelay,
	// Also reload invites on success: a sent invite reserves a Pending seat,
	// so it must appear in the Invites tab (and its count badge) immediately.
	refreshUsers: async () => {
		await Promise.all([refreshUsers(), loadInvites()]);
	},
	refreshLimit,
});

// Seat release — vacant-seat banner shown above the tabs.
const { releasing, releaseSeat } = useSeatRelease({
	refreshLimit,
	actionError,
	successMessage,
	clearMessageAfterDelay,
});

// Lifecycle
onMounted(async () => {
	await loadData();
	document.addEventListener("click", handleClickOutside);
	await handleStripeSeatReturn();
});

onUnmounted(() => {
	document.removeEventListener("click", handleClickOutside);
});
</script>

<style scoped>
.users-settings {
	width: 100%;
	max-width: 1100px;
}

/* Loading State */
.loading-state {
	display: flex;
	align-items: center;
	justify-content: center;
	gap: 0.75rem;
	padding: 3rem 1rem;
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

/* Error State */
.error-state {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 0.75rem;
	padding: 2rem 1rem;
	text-align: center;
	word-break: break-word;
	overflow-wrap: anywhere;
}

.error-icon {
	width: 2.5rem;
	height: 2.5rem;
	color: #dc2626;
	flex-shrink: 0;
}

.error-state p {
	color: var(--ql-text);
	margin: 0;
	max-width: 100%;
}

.retry-btn {
	padding: 0.5rem 1rem;
	font-size: 0.875rem;
	color: var(--ql-accent);
	background: transparent;
	border: 1px solid var(--ql-accent);
	border-radius: 0.375rem;
	cursor: pointer;
}

.retry-btn:hover {
	background: var(--ql-accent-soft);
}

/* Seat-cap upgrade banner — shown between UserLimitCard and the
   registered-users section when no seats remain on a bounded plan. */
/* Divider */
.divider {
	border: none;
	border-top: 1px solid var(--ql-border);
	margin: 1.5rem 0;
}

/* Messages */
.success-message,
.error-message {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.75rem 1rem;
	border-radius: 0.5rem;
	margin-bottom: 1rem;
	font-size: 0.875rem;
	word-break: break-word;
	overflow-wrap: anywhere;
}

.success-message {
	background: rgba(34, 197, 94, 0.1);
	border: 1px solid rgba(34, 197, 94, 0.3);
	color: #16a34a;
}

.error-message {
	background: rgba(239, 68, 68, 0.1);
	border: 1px solid rgba(239, 68, 68, 0.3);
	color: #dc2626;
}

.message-icon {
	width: 1rem;
	height: 1rem;
	flex-shrink: 0;
}

/* Suspended Note */
.suspended-note {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	margin-top: 1rem;
	padding: 0.75rem 1rem;
	background: rgba(234, 179, 8, 0.05);
	border: 1px solid rgba(234, 179, 8, 0.2);
	border-radius: 0.375rem;
	font-size: 0.75rem;
	color: #ca8a04;
}

.suspended-note svg {
	width: 1rem;
	height: 1rem;
	flex-shrink: 0;
}

</style>
