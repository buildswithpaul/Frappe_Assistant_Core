<template>
	<div v-if="creditBalance !== null" class="credit-card">
		<div class="credit-header">
			<span class="credit-label">Prepaid Credits</span>
			<span class="credit-balance-value">{{ formatCredits(creditBalance) }} credits</span>
		</div>
		<p class="credit-description">
			Credits are consumed at a 1:1 rate after your monthly quota is exhausted.
		</p>
		<button class="buy-credits-btn" @click="$emit('buy-credits')">
			<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M12 6v6m0 0v6m0-6h6m-6 0H6"
				/>
			</svg>
			Buy Credits
		</button>

		<!-- Transaction History -->
		<div v-if="visibleTransactions.length" class="txn-section">
			<div class="txn-header">
				<span class="txn-title">Recent Activity</span>
				<button
					v-if="transactions.length > 5"
					class="txn-toggle"
					@click="showAll = !showAll"
				>
					{{ showAll ? "Show less" : `Show all (${transactions.length})` }}
				</button>
			</div>
			<div class="txn-list">
				<div v-for="txn in visibleTransactions" :key="txn.name" class="txn-row">
					<div class="txn-main">
						<span class="txn-type-badge" :class="txn.type.toLowerCase()">
							{{ txn.type }}
						</span>
						<span class="txn-what">{{ describe(txn) }}</span>
						<span
							class="txn-credits"
							:class="(txn.credits || 0) > 0 ? 'positive' : 'negative'"
						>
							{{ (txn.credits || 0) > 0 ? "+" : ""
							}}{{ formatCredits(txn.credits || 0) }}
						</span>
					</div>
					<div class="txn-meta">
						<span>{{ formatTxnDate(txn.creation) }}</span>
						<!-- Credits carried over from an upgrade expire; credits you
						     bought outright do not. Saying which is which is the
						     whole reason this ledger is worth showing. -->
						<span v-if="(txn.credits || 0) > 0" class="txn-expiry">
							{{ expiryLabel(txn) }}
						</span>
					</div>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref, computed } from "vue";
import { formatCredits } from "@/composables/useFormatters";

const props = defineProps({
	creditBalance: { type: Number, default: null },
	transactions: { type: Array, default: () => [] },
});

defineEmits(["buy-credits"]);

const showAll = ref(false);

const visibleTransactions = computed(() => {
	if (showAll.value) return props.transactions;
	return props.transactions.slice(0, 5);
});

function formatTxnDate(dateStr) {
	if (!dateStr) return "";
	const d = new Date(dateStr);
	return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

const SOURCE_LABELS = {
	"Prepaid Purchase": "Credits you bought",
	"Plan Upgrade Credit": "Carried over from your previous plan",
	"Free Credits": "Included with your plan",
	"Referral Bonus": "Referral bonus",
	Promotional: "Promotional credits",
	"Admin Adjustment": "Adjustment",
	Transferred: "Transferred",
	"Template Revenue Share": "Template revenue share",
};

/** The customer's own words for where this came from, not the ledger's. */
function describe(txn) {
	if (txn.notes) return txn.notes;
	return SOURCE_LABELS[txn.source] || txn.source || "";
}

function expiryLabel(txn) {
	if (!txn.expires_at) return "Never expires";
	const on = new Date(txn.expires_at);
	const days = Math.ceil((on - new Date()) / 86400000);
	if (days < 0) return "Expired";
	const date = on.toLocaleDateString("en-US", {
		month: "short",
		day: "numeric",
		year: "numeric",
	});
	return days <= 30 ? `Expires ${date} (${days}d)` : `Expires ${date}`;
}
</script>

<style scoped>
.credit-card {
	background: var(--ql-surface, #fff);
	border: 1px solid var(--ql-border, #e5e7eb);
	border-radius: 0.5rem;
	padding: 1rem;
	margin-top: 0.75rem;
}

.credit-header {
	display: flex;
	justify-content: space-between;
	align-items: center;
	margin-bottom: 0.5rem;
}

.credit-label {
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text, #111827);
}

.credit-balance-value {
	font-size: 0.875rem;
	font-weight: 600;
	color: #7c3aed;
	font-family: ui-monospace, "SF Mono", SFMono-Regular, Menlo, monospace;
	font-variant-numeric: tabular-nums;
}

.credit-description {
	font-size: 0.75rem;
	color: var(--ql-text-muted, #6b7280);
	margin: 0 0 0.75rem;
	line-height: 1.4;
}

.buy-credits-btn {
	display: inline-flex;
	align-items: center;
	gap: 0.375rem;
	padding: 0.375rem 0.75rem;
	font-size: 0.75rem;
	font-weight: 500;
	color: #7c3aed;
	background: #f5f3ff;
	border: 1px solid #ddd6fe;
	border-radius: 0.375rem;
	cursor: pointer;
	transition: background 0.15s;
}

.buy-credits-btn:hover {
	background: #ede9fe;
}

/* Transaction History */
.txn-section {
	margin-top: 0.75rem;
	border-top: 1px solid var(--ql-border, #e5e7eb);
	padding-top: 0.75rem;
}

.txn-header {
	display: flex;
	justify-content: space-between;
	align-items: center;
	margin-bottom: 0.5rem;
}

.txn-title {
	font-size: 0.6875rem;
	font-weight: 600;
	color: var(--ql-text-muted, #6b7280);
	text-transform: uppercase;
	letter-spacing: 0.05em;
}

.txn-toggle {
	font-size: 0.6875rem;
	color: var(--ql-accent);
	background: none;
	border: none;
	cursor: pointer;
	padding: 0;
}

.txn-toggle:hover {
	text-decoration: underline;
}

.txn-list {
	display: flex;
	flex-direction: column;
	gap: 0.375rem;
}

.txn-row {
	display: flex;
	flex-direction: column;
	font-size: 0.75rem;
}

.txn-main { display: flex; align-items: center; gap: 0.5rem; }
.txn-what {
	flex: 1;
	min-width: 0;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
	font-size: 0.8125rem;
	color: var(--ql-ink-2, #6b7280);
}
.txn-meta {
	display: flex;
	justify-content: space-between;
	gap: 0.75rem;
	margin-top: 0.15rem;
	font-size: 0.75rem;
	color: var(--ql-ink-3, #9ca3af);
}
.txn-expiry { white-space: nowrap; }

.txn-type-badge {
	padding: 0.125rem 0.375rem;
	font-size: 0.625rem;
	font-weight: 500;
	border-radius: 9999px;
	text-transform: capitalize;
	flex-shrink: 0;
}

.txn-type-badge.purchase {
	color: #16a34a;
	background: rgba(22, 163, 74, 0.1);
}

.txn-type-badge.consumed {
	color: var(--ql-text-muted, #6b7280);
	background: var(--ql-subtle, #f3f4f6);
}

.txn-type-badge.refund {
	color: var(--ql-accent);
	background: var(--ql-accent-soft);
}

.txn-type-badge.expired {
	color: #f59e0b;
	background: rgba(245, 158, 11, 0.1);
}

.txn-credits {
	flex-shrink: 0;
	font-weight: 500;
	font-family: ui-monospace, "SF Mono", SFMono-Regular, Menlo, monospace;
	font-variant-numeric: tabular-nums;
}

.txn-credits.positive {
	color: #16a34a;
}

.txn-credits.negative {
	color: var(--ql-text, #111827);
}

.txn-date {
	color: var(--ql-text-muted, #6b7280);
	font-size: 0.6875rem;
	flex-shrink: 0;
}

.w-4 {
	width: 1rem;
	height: 1rem;
}
</style>
