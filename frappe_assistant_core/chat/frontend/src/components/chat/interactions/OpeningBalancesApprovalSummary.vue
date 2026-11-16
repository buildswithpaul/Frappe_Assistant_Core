<template>
	<!-- The opening entry the approval posts (#34433): its totals and the line to Temporary Opening
	     that balances it, which the generic fields hid behind "Show all fields". -->
	<dl class="opening-approval">
		<div v-if="input.company">
			<dt>{{ __("Company") }}</dt>
			<dd>{{ input.company }}</dd>
		</div>
		<div v-if="input.cut_off">
			<dt>{{ __("Cut-off") }}</dt>
			<dd>{{ input.cut_off }}</dd>
		</div>
		<div v-if="input.rows != null">
			<dt>{{ __("Accounts") }}</dt>
			<dd>{{ __("{0} rows", [input.rows]) }}</dd>
		</div>
		<div>
			<dt>{{ __("Total debit") }}</dt>
			<dd>{{ amount(input.total_debit) }}</dd>
		</div>
		<div>
			<dt>{{ __("Total credit") }}</dt>
			<dd>{{ amount(input.total_credit) }}</dd>
		</div>
		<div class="oa-wide">
			<dt>{{ __("Balancing line") }}</dt>
			<dd>{{ balancing }}</dd>
		</div>
		<div v-for="extra in extras" :key="extra.label" class="oa-wide">
			<dt>{{ extra.label }}</dt>
			<dd>{{ extra.text }}</dd>
		</div>
	</dl>
</template>

<script setup>
import { computed } from "vue";
import { __ } from "@/utils/i18n";

const props = defineProps({ input: { type: Object, required: true } });

const amount = (value) =>
	Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const balancing = computed(() => {
	const value = Number(props.input.balancing_amount || 0);
	if (!value) return __("None: debits and credits are equal");
	return value > 0
		? __("Debit {0} to Temporary Opening", [amount(value)])
		: __("Credit {0} to Temporary Opening", [amount(-value)]);
});

const extras = computed(() =>
	[
		[__("Covered by other imports"), props.input.covered_debit, props.input.covered_credit],
		[__("Left out"), props.input.excluded_debit, props.input.excluded_credit],
	]
		.filter(([, debit, credit]) => Number(debit || 0) || Number(credit || 0))
		.map(([label, debit, credit]) => ({
			label,
			text: __("Debits {0}, credits {1}", [amount(debit), amount(credit)]),
		}))
);
</script>

<style scoped>
.opening-approval {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
	gap: 6px 14px;
	margin: 6px 0 4px;
	/* the card's own side padding, as ApprovalDetails has: File / Into sat against the border (PR #392, L2) */
	padding: 0 16px;
	font-size: 13px;
}
.opening-approval dt { color: var(--ql-text-muted); font-weight: 500; }
.opening-approval dd { margin: 0; overflow-wrap: anywhere; color: var(--ql-text); }
.oa-wide { grid-column: 1 / -1; }
</style>
