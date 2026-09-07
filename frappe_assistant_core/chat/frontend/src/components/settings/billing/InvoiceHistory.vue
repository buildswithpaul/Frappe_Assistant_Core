<template>
	<div>
		<h3 class="section-title">Invoices</h3>

		<!-- Upcoming Invoice -->
		<div v-if="upcomingInvoice?.amount" class="upcoming-card">
			<div class="upcoming-row">
				<div class="upcoming-item">
					<span class="upcoming-label">Next billing date</span>
					<span class="upcoming-value">{{ formatDate(upcomingInvoice.date) }}</span>
				</div>
				<div class="upcoming-item">
					<span class="upcoming-label">Amount due</span>
					<span class="upcoming-value">{{
						formatCurrency(upcomingInvoice.amount, upcomingInvoice.currency)
					}}</span>
				</div>
			</div>
		</div>

		<!-- Invoice Table -->
		<div v-if="invoices.length" class="invoice-table-wrap">
			<table class="invoice-table">
				<thead>
					<tr>
						<th>Date</th>
						<th>Description</th>
						<th>Amount</th>
						<th>Status</th>
						<th></th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="invoice in invoices" :key="invoice.id || invoice.date">
						<td>{{ formatInvoiceDate(invoice) }}</td>
						<td>{{ invoice.description || invoice.plan || "Subscription" }}</td>
						<td class="amount-cell">{{ formatCurrency(invoice.amount, invoice.currency) }}</td>
						<td>
							<span class="status-badge" :class="invoice.status">
								{{ formatStatus(invoice.status) }}
							</span>
						</td>
						<td>
							<button
								v-if="isPaid(invoice)"
								type="button"
								class="download-link"
								title="Download PDF"
								aria-label="Download invoice PDF"
								@click="downloadInvoice(invoice)"
							>
								<svg
									class="w-4 h-4"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
								>
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
									/>
								</svg>
							</button>
						</td>
					</tr>
				</tbody>
			</table>
		</div>

		<!-- Empty State -->
		<div v-else class="empty-state">
			<svg class="empty-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
				/>
			</svg>
			<p class="empty-text">No invoices yet</p>
		</div>
	</div>
</template>

<script setup>
import { formatDate } from "@/composables/useFormatters";
import { api } from "@/api/client";

defineProps({
	invoices: { type: Array, default: () => [] },
	upcomingInvoice: { type: Object, default: null },
	formatCurrency: { type: Function, required: true },
	formatInvoiceDate: { type: Function, required: true },
	formatStatus: { type: Function, required: true },
});

// Only Paid invoices have a rendered PDF. Drafts / pending / failed
// rows get no download button (the endpoint would 4xx anyway — we
// keep the UI honest).
function isPaid(invoice) {
	return (invoice.status || "").toLowerCase() === "paid";
}

function downloadInvoice(invoice) {
	api.billing.downloadInvoicePdf(invoice.id);
}
</script>

<style scoped>
.section-title {
	font-size: 1rem;
	font-weight: 600;
	color: var(--ql-text);
	margin-bottom: 0.5rem;
}

.upcoming-card {
	padding: 1rem;
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	margin-bottom: 0.75rem;
}

.upcoming-row {
	display: flex;
	gap: 2rem;
}

.upcoming-item {
	display: flex;
	flex-direction: column;
	gap: 0.25rem;
}

.upcoming-label {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.upcoming-value {
	font-size: 0.9375rem;
	font-weight: 600;
	color: var(--ql-text);
	font-family: ui-monospace, "SF Mono", SFMono-Regular, Menlo, monospace;
	font-variant-numeric: tabular-nums;
}

.invoice-table-wrap {
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	overflow: hidden;
}

.invoice-table {
	width: 100%;
	border-collapse: collapse;
}

.invoice-table th,
.invoice-table td {
	padding: 0.625rem 0.75rem;
	text-align: left;
}

.invoice-table th {
	font-size: 0.6875rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.05em;
	background: var(--ql-bg);
	border-bottom: 1px solid var(--ql-border);
}

.invoice-table td {
	font-size: 0.8125rem;
	color: var(--ql-text);
	border-bottom: 1px solid var(--ql-border);
}

.invoice-table tr:last-child td {
	border-bottom: none;
}

.invoice-table td.amount-cell {
	font-family: ui-monospace, "SF Mono", SFMono-Regular, Menlo, monospace;
	font-variant-numeric: tabular-nums;
}

.status-badge {
	padding: 0.1875rem 0.5rem;
	font-size: 0.6875rem;
	font-weight: 500;
	border-radius: 9999px;
	text-transform: capitalize;
}

.status-badge.paid,
.status-badge.active {
	color: var(--ql-success, #22c55e);
	background: rgba(34, 197, 94, 0.1);
}

.status-badge.pending {
	color: #f59e0b;
	background: rgba(245, 158, 11, 0.1);
}

.status-badge.failed {
	color: var(--ql-danger, #ef4444);
	background: rgba(239, 68, 68, 0.1);
}

.download-link {
	display: flex;
	align-items: center;
	color: var(--ql-accent);
	text-decoration: none;
	background: transparent;
	border: none;
	padding: 0;
	cursor: pointer;
}

.download-link:hover {
	opacity: 0.8;
}

.empty-state {
	display: flex;
	flex-direction: column;
	align-items: center;
	padding: 2rem;
	text-align: center;
	background: var(--ql-bg);
	border: 1px dashed var(--ql-border);
	border-radius: 0.5rem;
}

.empty-icon {
	width: 2.5rem;
	height: 2.5rem;
	color: var(--ql-text-muted);
	margin-bottom: 0.5rem;
}

.empty-text {
	font-size: 0.875rem;
	color: var(--ql-text-muted);
}

.w-4 {
	width: 1rem;
	height: 1rem;
}
</style>
