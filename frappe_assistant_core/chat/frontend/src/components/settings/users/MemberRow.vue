<template>
	<!-- Main row -->
	<tr
		:class="{
			'is-current': isCurrent,
			expandable: true,
			expanded: expanded,
		}"
		@click="$emit('open-member', user)"
	>
		<td class="member-cell">
			<div class="member-info">
				<div>
					<span class="member-name">{{ user.display_name || user.user_id }}</span>
					<span v-if="user.display_name" class="member-email">{{ user.user_id }}</span>
					<span v-if="isCurrent" class="you-badge">You</span>
				</div>
			</div>
		</td>
		<td>
			<RoleBadge :role="user.role || 'Member'" />
		</td>
		<td>
			<span
				class="status-badge"
				:class="'status-' + (user.status || 'Active').toLowerCase()"
			>
				{{ user.status || "Active" }}
			</span>
		</td>
		<td class="activity-cell">
			<span class="activity-time">{{ formatRelativeTime(user.last_activity) }}</span>
			<span
				v-if="isIdle(user.last_activity)"
				class="idle-flag"
				title="Inactive for 30+ days"
			>
				<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
					/>
				</svg>
				Idle
			</span>
		</td>
		<td class="credits-cell">
			<div class="credits-display" v-if="user.status === 'Active'">
				<div class="credits-bar-mini" v-if="creditLimit > 0">
					<div
						class="credits-bar-fill"
						:style="{ width: creditPercent + '%' }"
						:class="creditBarClass"
					></div>
				</div>
				<span class="credits-number">{{
					formatCreditsShort(user.credits_used_this_month || 0)
				}}</span>
			</div>
			<span v-else class="credits-na">&mdash;</span>
		</td>
		<td class="limit-cell">
			<span v-if="creditLimit > 0" class="limit-value">
				{{ formatCreditsShort(creditLimit) }}
			</span>
			<span v-else class="limit-none">Shared</span>
		</td>
		<td class="actions-cell" @click.stop>
			<div class="actions-menu" v-if="!isCurrent">
				<button
					class="menu-trigger"
					@click.stop="$emit('toggle-menu', user.user_id)"
					aria-label="Member actions"
				>
					<svg class="menu-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z"
						/>
					</svg>
				</button>
				<div v-if="menuOpen" class="dropdown-menu">
					<button class="dropdown-item" @click="$emit('toggle-expand', user.user_id)">
						Set credit limit
					</button>
					<button
						v-if="user.status === 'Active'"
						class="dropdown-item"
						@click="$emit('suspend', user.user_id)"
						:disabled="actionLoading"
					>
						Suspend
					</button>
					<button
						class="dropdown-item danger"
						@click="$emit('remove', user.user_id)"
						:disabled="actionLoading"
					>
						Remove
					</button>
				</div>
			</div>
			<span v-else class="no-actions-hint">&mdash;</span>
		</td>
	</tr>

	<!-- Expanded credit-limit row (click stopped so it doesn't open drawer) -->
	<tr v-if="expanded" class="expanded-row" @click.stop>
		<td colspan="7">
			<div class="expanded-content">
				<div class="expanded-section">
					<label class="expanded-label">Monthly Credit Limit</label>
					<div class="limit-input-row">
						<input
							:value="editCreditLimit"
							@input="
								$emit(
									'update:editCreditLimit',
									parseFloat($event.target.value) || 0
								)
							"
							type="number"
							min="0"
							step="1000"
							class="limit-input"
							placeholder="0 (shared pool)"
						/>
						<button
							class="save-limit-btn"
							@click.stop="$emit('save-credit-limit', user.user_id)"
							:disabled="savingLimit"
						>
							{{ savingLimit ? "Saving..." : "Save" }}
						</button>
					</div>
					<p class="limit-hint">
						Set to 0 for unlimited (draws from shared team pool)
					</p>
				</div>
			</div>
		</td>
	</tr>
</template>

<script setup>
import { computed } from "vue";
import RoleBadge from "./RoleBadge.vue";
import { isIdle } from "./memberHelpers";
import { formatRelativeTime } from "@/composables/useFormatters";

const props = defineProps({
	user: { type: Object, required: true },
	isCurrent: { type: Boolean, default: false },
	expanded: { type: Boolean, default: false },
	menuOpen: { type: Boolean, default: false },
	editCreditLimit: { type: Number, default: 0 },
	savingLimit: { type: Boolean, default: false },
	actionLoading: { type: Boolean, default: false },
});

defineEmits([
	"open-member",
	"toggle-menu",
	"toggle-expand",
	"suspend",
	"remove",
	"save-credit-limit",
	"update:editCreditLimit",
]);

const creditLimit = computed(() => toFloat(props.user.monthly_credit_limit || 0));

const creditPercent = computed(() => {
	if (creditLimit.value <= 0) return 0;
	const used = toFloat(props.user.credits_used_this_month || 0);
	return Math.min(100, (used / creditLimit.value) * 100);
});

const creditBarClass = computed(() => {
	if (creditPercent.value >= 100) return "bar-danger";
	if (creditPercent.value >= 80) return "bar-warning";
	return "";
});

function formatCreditsShort(val) {
	if (!val || val === 0) return "0";
	const n = Number(val);
	if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
	if (n >= 1000) return (n / 1000).toFixed(1) + "K";
	return n.toLocaleString();
}

function toFloat(v) {
	return parseFloat(v) || 0;
}
</script>

<style scoped>
td {
	padding: 0.75rem 1rem;
	border-bottom: 1px solid var(--ql-border);
	color: var(--ql-text);
}

tr.is-current {
	background: var(--ql-accent-soft);
}

tr.expandable {
	cursor: pointer;
}

tr.expandable:hover {
	background: var(--ql-subtle);
}

tr.expanded {
	background: var(--ql-accent-soft);
}

/* Member cell */
.member-cell {
	max-width: 220px;
}

.member-info {
	display: flex;
	align-items: center;
	gap: 0.5rem;
}

.member-info > div {
	display: flex;
	flex-direction: column;
	gap: 0.125rem;
}

.member-name {
	font-weight: 500;
	word-break: break-word;
}

.member-email {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	word-break: break-all;
}

.you-badge {
	display: inline-block;
	padding: 0.125rem 0.375rem;
	font-size: 0.625rem;
	font-weight: 500;
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
	border-radius: 9999px;
	margin-top: 0.25rem;
	width: fit-content;
}

/* Status badge */
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

/* Activity / idle */
.activity-cell {
	min-width: 120px;
}

.activity-time {
	font-size: 0.8125rem;
	color: var(--ql-text);
}

.idle-flag {
	display: inline-flex;
	align-items: center;
	gap: 0.2rem;
	margin-left: 0.4rem;
	padding: 0.05rem 0.4rem;
	font-size: 0.66rem;
	font-weight: 600;
	color: var(--ql-warning);
	background: var(--ql-gold-soft);
	border-radius: 9999px;
	vertical-align: middle;
}

.idle-flag svg {
	width: 0.7rem;
	height: 0.7rem;
}

/* Credits column */
.credits-cell {
	min-width: 100px;
}

.credits-display {
	display: flex;
	flex-direction: column;
	gap: 0.25rem;
}

.credits-bar-mini {
	width: 60px;
	height: 4px;
	background: var(--ql-border);
	border-radius: 2px;
	overflow: hidden;
}

.credits-bar-fill {
	height: 100%;
	background: var(--ql-accent);
	border-radius: 2px;
	transition: width 0.3s ease;
}

.credits-bar-fill.bar-warning {
	background: #eab308;
}
.credits-bar-fill.bar-danger {
	background: #ef4444;
}

.credits-number {
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text);
}

.credits-na {
	color: var(--ql-text-muted);
}

.limit-cell {
	min-width: 70px;
}

.limit-value {
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text);
}

.limit-none {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

/* Expanded row */
.expanded-row td {
	padding: 0 !important;
	border-bottom: 1px solid var(--ql-border);
}

.expanded-content {
	padding: 1rem 1.25rem 1.25rem;
	background: var(--ql-subtle);
	display: flex;
	flex-direction: column;
	gap: 1rem;
}

.expanded-section {
	display: flex;
	flex-wrap: wrap;
	align-items: center;
	gap: 0.5rem;
}

.expanded-label {
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.03em;
}

.limit-input-row {
	display: flex;
	gap: 0.5rem;
	align-items: center;
}

.limit-input {
	width: 120px;
	padding: 0.375rem 0.625rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	outline: none;
}

.limit-input:focus {
	border-color: var(--ql-accent);
}

.save-limit-btn {
	padding: 0.375rem 0.75rem;
	font-size: 0.75rem;
	font-weight: 500;
	color: white;
	background: var(--ql-accent);
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
}

.save-limit-btn:hover:not(:disabled) {
	opacity: 0.9;
}
.save-limit-btn:disabled {
	opacity: 0.5;
	cursor: not-allowed;
}

.limit-hint {
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	width: 100%;
}

/* Actions menu */
.actions-cell {
	width: 50px;
	text-align: right;
}

.actions-menu {
	position: relative;
}

.menu-trigger {
	padding: 0.375rem;
	background: transparent;
	border: none;
	border-radius: 0.25rem;
	cursor: pointer;
	color: var(--ql-text-muted);
	transition: all 0.15s ease;
}

.menu-trigger:hover {
	background: var(--ql-subtle);
	color: var(--ql-text);
}

.menu-icon {
	width: 1.25rem;
	height: 1.25rem;
}

.dropdown-menu {
	position: absolute;
	right: 0;
	top: 100%;
	margin-top: 0.25rem;
	min-width: 140px;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
	z-index: 1100;
	overflow: hidden;
}

.dropdown-item {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	width: 100%;
	padding: 0.5rem 0.75rem;
	font-size: 0.875rem;
	color: var(--ql-text);
	background: transparent;
	border: none;
	cursor: pointer;
	text-align: left;
	transition: background 0.15s ease;
}

.dropdown-item:hover:not(:disabled) {
	background: var(--ql-subtle);
}

.dropdown-item:disabled {
	opacity: 0.5;
	cursor: not-allowed;
}

.dropdown-item.danger {
	color: #dc2626;
}

.dropdown-item.danger:hover:not(:disabled) {
	background: rgba(239, 68, 68, 0.1);
}

.no-actions-hint {
	color: var(--ql-text-muted);
	font-size: 0.875rem;
}

/* Responsive — hide Credits Used (5th) + Limit (6th) cells on narrow screens
   (the matching <th> are hidden in MembersTab). The expanded row spans all
   columns via colspan and is unaffected. */
@media (max-width: 720px) {
	tr:not(.expanded-row) > td.credits-cell,
	tr:not(.expanded-row) > td.limit-cell {
		display: none;
	}

	.member-cell {
		max-width: 150px;
	}
}
</style>
