<template>
	<div class="my-packs-view">
		<ListPageShell>
			<template #header>
				<ListHeaderBand
					title="My Packs"
					:stat="`${enabledPacks.length} active · ${freeGrantsUsed} of ${freeGrantAllowance} free used`"
				/>
			</template>

			<!-- Empty state is a full-width banner, not a card — keep it out
			     of the card grid so it spans the row above the grid. -->
			<template #toolbar>
				<EmptyState
					v-if="!loading && !enabledPacks.length"
					title="No packs activated yet"
					description="Packs you activate, purchase, or receive from your admin appear here."
					cta="Browse Industry Packs"
					@cta="$router.push('/settings/packs')"
				/>
			</template>

			<PackContents
				v-for="p in enabledPacks"
				:key="p.pack_id"
				:pack="p"
				class="pack-contents-item"
			/>
		</ListPageShell>

		<div class="my-packs-detail">
			<section class="section">
				<h3>Purchase history</h3>
				<p v-if="!purchases.length" class="empty">No purchases yet.</p>
				<table v-else class="history-table">
					<thead>
						<tr>
							<th>Pack</th>
							<th>Amount</th>
							<th>Paid on</th>
							<th>Invoice</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="p in purchases" :key="p.name">
							<td>{{ p.pack_display_name || p.pack }}</td>
							<td class="amount">{{ formatAmount(p.amount, p.currency) }}</td>
							<td>{{ formatDate(p.paid_at) }}</td>
							<td>
								<a
									v-if="p.ar_invoice"
									:href="invoiceUrl(p.ar_invoice)"
									target="_blank"
									rel="noopener"
									>Download</a
								>
								<span v-else>—</span>
							</td>
						</tr>
					</tbody>
				</table>
			</section>

			<section class="section">
				<h3>Free pack allowance</h3>
				<p>{{ freeGrantsUsed }} of {{ freeGrantAllowance }} used.</p>
				<p v-if="freeGrantAllowance === 0" class="note">
					Your plan does not include any free packs. Purchase packs
					individually from the marketplace.
				</p>
				<p v-else-if="freeGrantsUsed >= freeGrantAllowance" class="note">
					You've used your free pack allowance. Additional packs can be
					purchased.
				</p>
			</section>
		</div>
	</div>
</template>

<script setup>
import { onMounted, computed } from "vue";
import { storeToRefs } from "pinia";
import { usePacksStore } from "@/stores/packsStore";
import ListPageShell from "@/components/common/list/ListPageShell.vue";
import ListHeaderBand from "@/components/common/list/ListHeaderBand.vue";
import EmptyState from "@/components/common/list/EmptyState.vue";
import PackContents from "@/components/settings/packs/PackContents.vue";

const packsStore = usePacksStore();
const { items, purchases, loading } = storeToRefs(packsStore);

onMounted(async () => {
	await Promise.all([packsStore.load(), packsStore.loadPurchases()]);
});

const enabledPacks = computed(() =>
	items.value.filter((p) => p.is_owned && p.enabled),
);

const freeGrantsUsed = computed(
	() => items.value.filter((p) => p.acquisition === "free_grant").length,
);

const freeGrantAllowance = computed(() => {
	// Derive from any pack that surfaces is_free_grant_available — the
	// flag is true when has_free_slot is true (i.e. allowance not exhausted).
	// If any pack has it true, allowance > used. If none, allowance == used.
	const someAvailable = items.value.some((p) => p.is_free_grant_available);
	return someAvailable ? freeGrantsUsed.value + 1 : freeGrantsUsed.value;
});

function formatAmount(amount, currency) {
	const symbol = currency === "USD" ? "$" : "₹";
	return `${symbol}${Number(amount).toFixed(2)}`;
}

function formatDate(iso) {
	if (!iso) return "—";
	const d = new Date(iso);
	return d.toLocaleDateString();
}

function invoiceUrl(invoice_name) {
	return `/api/method/frappe.utils.print_format.download_pdf?doctype=AR%20Invoice&name=${encodeURIComponent(invoice_name)}&format=GST%20Tax%20Invoice`;
}
</script>

<style scoped>
.my-packs-view {
	display: flex;
	flex-direction: column;
	min-height: 100%;
	background: var(--ql-bg);
}
.my-packs-detail {
	max-width: 1200px;
	margin: 24px auto 0;
	padding: 0 24px 24px;
	width: 100%;
}
.section {
	margin-bottom: 32px;
}
.section h3 {
	margin: 0 0 12px 0;
	font-size: 16px;
	font-weight: 600;
	color: var(--ql-text);
}
.empty {
	color: var(--ql-text-muted);
	font-style: italic;
}
.empty a {
	color: var(--ql-accent);
	text-decoration: none;
}
.empty a:hover {
	text-decoration: underline;
}
.note {
	color: var(--ql-text-muted);
	font-size: 13px;
	margin-top: 4px;
}
/* Anchor each card to the top of its grid cell so its height follows its own
   content. Without this, the grid stretches every card in a row to match the
   tallest one, so expanding one pack would stretch its collapsed row-mate. */
.pack-contents-item {
	margin-bottom: 10px;
	align-self: start;
}
.history-table {
	width: 100%;
	border-collapse: collapse;
}
.history-table th,
.history-table td {
	padding: 10px 12px;
	text-align: left;
	border-bottom: 1px solid var(--ql-border);
}
.history-table th {
	font-size: 12px;
	text-transform: uppercase;
	color: var(--ql-text-muted);
	background: var(--ql-subtle);
}
.history-table td.amount {
	font-family: ui-monospace, "SF Mono", monospace;
}
.history-table a {
	color: var(--ql-accent);
	text-decoration: none;
}
.history-table a:hover {
	text-decoration: underline;
}
</style>
