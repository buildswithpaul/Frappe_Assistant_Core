<template>
	<Teleport to="body">
		<Transition name="drawer">
			<div v-if="open && member" class="drawer-overlay" @click.self="$emit('close')">
				<aside
					class="drawer-panel"
					role="dialog"
					aria-modal="true"
					:aria-label="`Member details for ${displayName}`"
				>
					<!-- Header: close -->
					<div class="drawer-topbar">
						<span class="drawer-eyebrow">Member</span>
						<button class="drawer-close" @click="$emit('close')" aria-label="Close">
							&times;
						</button>
					</div>

					<!-- Identity header -->
					<div class="identity">
						<div class="avatar" :class="'avatar-' + roleKey">{{ initial }}</div>
						<div class="identity-body">
							<div class="identity-line">
								<span class="identity-name">{{ displayName }}</span>
								<RoleBadge :role="member.role || 'Member'" />
								<span v-if="isSelf" class="you-badge">You</span>
							</div>
							<div class="identity-meta">
								<span class="meta-email">{{ member.user_id }}</span>
								<template v-if="member.department">
									<span class="meta-dot">·</span>
									<span>{{ member.department }}</span>
								</template>
							</div>
							<div class="identity-tags">
								<span
									class="status-badge"
									:class="'status-' + (member.status || 'Active').toLowerCase()"
								>
									{{ member.status || "Active" }}
								</span>
								<span v-if="joinedLabel" class="joined-label">{{ joinedLabel }}</span>
							</div>
						</div>
					</div>

					<!-- At-a-glance tiles -->
					<div class="tiles">
						<div class="tile">
							<span class="tile-label">Last Active</span>
							<span class="tile-value">
								{{ lastActiveLabel }}
								<span v-if="idle" class="idle-flag" title="Inactive for 30+ days">
									Idle
								</span>
							</span>
						</div>
						<div class="tile">
							<span class="tile-label">Credits this period</span>
							<span class="tile-value">{{
								formatCredits(member.credits_used_this_month || 0)
							}}</span>
						</div>
						<div v-if="hasMcpCount" class="tile">
							<span class="tile-label">MCP Servers</span>
							<span class="tile-value">{{ member.mcp_server_count }}</span>
						</div>
					</div>

					<!-- Manage -->
					<div class="manage">
						<h4 class="manage-title">Manage</h4>

						<!-- Role: read-only in v1 -->
						<div class="manage-row">
							<div class="manage-row-text">
								<span class="manage-label">Role</span>
								<span class="manage-hint">Role changes are coming soon.</span>
							</div>
							<!-- TODO: role-change endpoint (follow-up) -->
							<RoleBadge :role="member.role || 'Member'" />
						</div>

						<!-- Monthly credit limit -->
						<div class="manage-block">
							<label class="manage-label" :for="limitId">Monthly credit limit</label>
							<div class="limit-row">
								<input
									:id="limitId"
									v-model.number="creditLimitDraft"
									type="number"
									min="0"
									step="1000"
									class="limit-input"
									placeholder="0 (shared pool)"
								/>
								<button
									class="btn-primary"
									:disabled="savingLimit"
									@click="emitSaveLimit"
								>
									{{ savingLimit ? "Saving..." : "Save" }}
								</button>
							</div>
							<p class="manage-hint">
								Set to 0 for unlimited (draws from the shared team pool).
							</p>
						</div>

						<!-- Destructive actions (hidden for self) -->
						<div v-if="!isSelf" class="manage-actions">
							<button
								v-if="member.status === 'Active'"
								class="btn-warning"
								:disabled="actionLoading"
								@click="$emit('suspend', member.user_id)"
							>
								Suspend
							</button>
							<button
								class="btn-danger"
								:disabled="actionLoading"
								@click="$emit('remove', member.user_id)"
							>
								Remove
							</button>
						</div>
					</div>
				</aside>
			</div>
		</Transition>
	</Teleport>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from "vue";
import RoleBadge from "./RoleBadge.vue";
import { isIdle } from "./memberHelpers";
import { formatRelativeTime, formatDate, formatCredits } from "@/composables/useFormatters";

const props = defineProps({
	member: { type: Object, default: null },
	open: { type: Boolean, default: false },
	// Current session user — suspend/remove are hidden when viewing yourself
	// (mirrors the self-action guard in MemberRow).
	currentUser: { type: String, default: "" },
	// Wired to the parent's confirm-flow loading + credit-limit saving flags.
	actionLoading: { type: Boolean, default: false },
	savingLimit: { type: Boolean, default: false },
});

const emit = defineEmits(["close", "suspend", "remove", "save-credit-limit"]);

const limitId = "member-drawer-credit-limit";

// Local draft for the credit-limit input — reset whenever a new member opens.
const creditLimitDraft = ref(0);
watch(
	() => [props.member?.user_id, props.open],
	() => {
		creditLimitDraft.value = parseFloat(props.member?.monthly_credit_limit || 0) || 0;
	},
	{ immediate: true }
);

const displayName = computed(
	() => props.member?.display_name || props.member?.user_id || ""
);

const initial = computed(() => {
	const src = displayName.value || "?";
	return src.trim().charAt(0).toUpperCase() || "?";
});

const roleKey = computed(() => (props.member?.role || "Member").toLowerCase());

const isSelf = computed(
	() => !!props.currentUser && props.member?.user_id === props.currentUser
);

const idle = computed(() => isIdle(props.member?.last_activity));

const lastActiveLabel = computed(
	() => formatRelativeTime(props.member?.last_activity) || "Never"
);

const hasMcpCount = computed(
	() => props.member?.mcp_server_count !== undefined && props.member?.mcp_server_count !== null
);

// "Invited <date>" for Pending members, otherwise "Joined <date>" — only when
// a created_at timestamp is present on the member object.
const joinedLabel = computed(() => {
	const ts = props.member?.created_at;
	if (!ts) return "";
	const verb = props.member?.status === "Pending" ? "Invited" : "Joined";
	return `${verb} ${formatDate(ts)}`;
});

function emitSaveLimit() {
	emit("save-credit-limit", {
		userId: props.member.user_id,
		limit: creditLimitDraft.value || 0,
	});
}

// Escape closes the drawer (only while open, so it doesn't swallow Esc for
// other components when the drawer is hidden).
function onKeydown(e) {
	if (e.key === "Escape" && props.open) {
		emit("close");
	}
}

onMounted(() => document.addEventListener("keydown", onKeydown));
onUnmounted(() => document.removeEventListener("keydown", onKeydown));
</script>

<style scoped>
.drawer-overlay {
	position: fixed;
	inset: 0;
	background: rgba(0, 0, 0, 0.45);
	display: flex;
	justify-content: flex-end;
	z-index: 1200;
}

.drawer-panel {
	width: 440px;
	max-width: 92vw;
	height: 100%;
	background: var(--ql-surface);
	border-left: 1px solid var(--ql-border);
	box-shadow: -8px 0 32px rgba(0, 0, 0, 0.18);
	display: flex;
	flex-direction: column;
	overflow-y: auto;
	padding: 1.25rem 1.5rem 2rem;
}

/* Topbar */
.drawer-topbar {
	display: flex;
	align-items: center;
	justify-content: space-between;
	margin-bottom: 1.25rem;
}

.drawer-eyebrow {
	font-size: 0.6875rem;
	font-weight: 600;
	letter-spacing: 0.06em;
	text-transform: uppercase;
	color: var(--ql-text-muted);
}

.drawer-close {
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

.drawer-close:hover {
	color: var(--ql-text);
}

/* Identity */
.identity {
	display: flex;
	gap: 0.875rem;
	align-items: flex-start;
	margin-bottom: 1.5rem;
}

.avatar {
	flex-shrink: 0;
	width: 3rem;
	height: 3rem;
	border-radius: 9999px;
	display: flex;
	align-items: center;
	justify-content: center;
	font-size: 1.25rem;
	font-weight: 600;
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
}

.avatar-owner {
	background: var(--ql-gold-soft);
	color: #8a6d12;
}

[data-theme="dark"] .avatar-owner {
	color: #e3c869;
}

.identity-body {
	min-width: 0;
	flex: 1;
}

.identity-line {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	flex-wrap: wrap;
}

.identity-name {
	font-size: 1.0625rem;
	font-weight: 600;
	color: var(--ql-text);
	word-break: break-word;
}

.you-badge {
	display: inline-block;
	padding: 0.125rem 0.375rem;
	font-size: 0.625rem;
	font-weight: 500;
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
	border-radius: 9999px;
}

.identity-meta {
	display: flex;
	align-items: center;
	gap: 0.375rem;
	flex-wrap: wrap;
	margin-top: 0.375rem;
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
}

.meta-email {
	word-break: break-all;
}

.meta-dot {
	opacity: 0.6;
}

.identity-tags {
	display: flex;
	align-items: center;
	gap: 0.625rem;
	flex-wrap: wrap;
	margin-top: 0.625rem;
}

.joined-label {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

/* Status badge — mirrors MemberRow */
.status-badge {
	display: inline-block;
	padding: 0.125rem 0.5rem;
	font-size: 0.75rem;
	font-weight: 500;
	border-radius: 9999px;
}

.status-active {
	background: rgba(34, 197, 94, 0.1);
	color: #16a34a;
}

.status-pending {
	background: var(--ql-gold-soft);
	color: var(--ql-warning);
}

.status-suspended {
	background: rgba(234, 179, 8, 0.1);
	color: #ca8a04;
}

.status-revoked {
	background: rgba(239, 68, 68, 0.1);
	color: #dc2626;
}

/* Tiles */
.tiles {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
	gap: 0.625rem;
	margin-bottom: 1.5rem;
}

.tile {
	display: flex;
	flex-direction: column;
	gap: 0.3rem;
	padding: 0.75rem 0.875rem;
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
}

.tile-label {
	font-size: 0.6875rem;
	font-weight: 500;
	text-transform: uppercase;
	letter-spacing: 0.03em;
	color: var(--ql-text-muted);
}

.tile-value {
	display: inline-flex;
	align-items: center;
	gap: 0.4rem;
	font-size: 0.9375rem;
	font-weight: 600;
	color: var(--ql-text);
}

.idle-flag {
	padding: 0.05rem 0.4rem;
	font-size: 0.625rem;
	font-weight: 600;
	color: var(--ql-warning);
	background: var(--ql-gold-soft);
	border-radius: 9999px;
}

/* Manage */
.manage {
	border-top: 1px solid var(--ql-border);
	padding-top: 1.25rem;
}

.manage-title {
	margin: 0 0 1rem;
	font-size: 0.8125rem;
	font-weight: 600;
	text-transform: uppercase;
	letter-spacing: 0.03em;
	color: var(--ql-text-muted);
}

.manage-row {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 1rem;
	padding-bottom: 1rem;
	margin-bottom: 1rem;
	border-bottom: 1px solid var(--ql-border);
}

.manage-row-text {
	display: flex;
	flex-direction: column;
	gap: 0.2rem;
}

.manage-block {
	margin-bottom: 1.25rem;
}

.manage-label {
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text);
}

.manage-hint {
	margin: 0.4rem 0 0;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	line-height: 1.4;
}

.limit-row {
	display: flex;
	gap: 0.5rem;
	align-items: center;
	margin-top: 0.5rem;
}

.limit-input {
	flex: 1;
	min-width: 0;
	padding: 0.5rem 0.75rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	outline: none;
	transition: border-color 0.15s ease;
}

.limit-input:focus {
	border-color: var(--ql-accent);
}

.manage-actions {
	display: flex;
	gap: 0.625rem;
	margin-top: 0.5rem;
}

/* Buttons */
.btn-primary {
	padding: 0.5rem 1rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: white;
	background: var(--ql-accent);
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
	white-space: nowrap;
	transition: all 0.15s ease;
}

.btn-primary:hover:not(:disabled) {
	background: var(--ql-accent-hover);
}

.btn-warning {
	padding: 0.5rem 1rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: #ca8a04;
	background: transparent;
	border: 1px solid rgba(234, 179, 8, 0.4);
	border-radius: 0.375rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.btn-warning:hover:not(:disabled) {
	background: rgba(234, 179, 8, 0.1);
}

.btn-danger {
	padding: 0.5rem 1rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: #dc2626;
	background: transparent;
	border: 1px solid rgba(239, 68, 68, 0.4);
	border-radius: 0.375rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.btn-danger:hover:not(:disabled) {
	background: rgba(239, 68, 68, 0.1);
}

.btn-primary:disabled,
.btn-warning:disabled,
.btn-danger:disabled {
	opacity: 0.5;
	cursor: not-allowed;
}

/* Slide-in transition */
.drawer-enter-active,
.drawer-leave-active {
	transition: opacity 0.2s ease;
}

.drawer-enter-active .drawer-panel,
.drawer-leave-active .drawer-panel {
	transition: transform 0.22s ease;
}

.drawer-enter-from,
.drawer-leave-to {
	opacity: 0;
}

.drawer-enter-from .drawer-panel,
.drawer-leave-to .drawer-panel {
	transform: translateX(100%);
}

@media (max-width: 520px) {
	.drawer-panel {
		width: 100vw;
		max-width: 100vw;
	}
}
</style>
