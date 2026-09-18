<template>
	<div class="invoices-tab">
		<InvoiceHistory
			:invoices="invoices"
			:upcoming-invoice="upcomingInvoice"
			:format-currency="formatCurrency"
			:format-invoice-date="formatInvoiceDate"
			:format-status="formatStatus"
			:outstanding-invoice-id="outstandingInvoiceId"
			@pay="$emit('pay')"
		/>
	</div>
</template>

<script setup>
import InvoiceHistory from "./InvoiceHistory.vue";

defineProps({
	invoices: { type: Array, default: () => [] },
	upcomingInvoice: { type: Object, default: null },
	formatCurrency: { type: Function, required: true },
	formatInvoiceDate: { type: Function, required: true },
	formatStatus: { type: Function, required: true },
	outstandingInvoiceId: { type: String, default: null },
});

defineEmits(["pay"]);
</script>

<style scoped>
.invoices-tab {
	padding-top: 1.5rem;
}
</style>
