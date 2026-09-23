<template>
	<p class="hosted-notice">
		<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
			stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
			<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
			<polyline points="15 3 21 3 21 9" />
			<line x1="10" y1="14" x2="21" y2="3" />
		</svg>
		<span>
			You'll be taken to <strong>{{ host }}</strong> to pay, and brought back here
			afterwards. The full amount, including tax, is shown before you're charged.
		</span>
	</p>
</template>

<script setup>
// Payments are collected on FAC Cloud's own site, never on this one — a
// payment gateway is onboarded against a single declared website. Leaving
// someone's own ERP for a domain they don't recognise is exactly the moment
// a purchase gets abandoned, so say it before they click, not after.
defineProps({
	host: {
		type: String,
		default: "FAC Cloud",
	},
});
</script>

<style scoped>
.hosted-notice {
	display: flex;
	gap: 0.5rem;
	align-items: flex-start;
	margin: 0.75rem 0 0;
	font-size: 0.8125rem;
	line-height: 1.5;
	color: var(--ql-ink-2, #6b7280);
}
.hosted-notice svg {
	flex: 0 0 14px;
	width: 14px;
	height: 14px;
	margin-top: 0.15rem;
}
.hosted-notice strong {
	font-weight: 600;
	color: var(--ql-ink, #111827);
}
</style>
