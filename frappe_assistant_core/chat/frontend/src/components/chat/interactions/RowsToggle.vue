<template>
	<span class="child-rows">
		<button type="button" class="rows-toggle" :aria-expanded="String(open)" @click="open = !open">
			{{ rows.length === 1 ? __("1 row") : __("{0} rows", [rows.length]) }}
		</button>
		<table v-if="open" class="rows-table">
			<thead>
				<tr>
					<th v-for="key in columns" :key="key" scope="col">{{ columnLabel(key) }}</th>
				</tr>
			</thead>
			<tbody>
				<tr v-for="(row, i) in rows" :key="i">
					<td v-for="key in columns" :key="key">
						<template v-if="key in row">
							<LongValue v-if="isLongValue(row[key])" :value="row[key]" :code="isCodeKey(key)" />
							<template v-else>{{ cellText(row[key]) }}</template>
						</template>
					</td>
				</tr>
			</tbody>
		</table>
	</span>
</template>

<script setup>
// A record's child table in a list of records: its row count, opening to every row with
// every key it sends (name and _delete included, so a removed row shows as removed).
import { computed, ref } from "vue";
import { __ } from "@/utils/i18n";
import LongValue from "./LongValue.vue";
import { cellText, columnLabel, isCodeKey, isLongValue } from "./helpers";

const props = defineProps({
	rows: { type: Array, required: true },
});

const open = ref(false);
const columns = computed(() => [...new Set(props.rows.flatMap((row) => Object.keys(row)))]);
</script>

<style scoped>
.child-rows {
	display: inline-flex;
	flex-direction: column;
	align-items: flex-start;
	gap: 4px;
}

.rows-toggle {
	background: transparent;
	border: none;
	padding: 0;
	font-size: 11px;
	color: var(--ql-accent);
	cursor: pointer;
}

.rows-toggle::after {
	content: " ›";
}

.rows-toggle[aria-expanded="true"]::after {
	content: " ‹";
}

.rows-table {
	border-collapse: collapse;
	font-size: 11px;
	border: 1px solid var(--ql-border);
}

.rows-table th,
.rows-table td {
	padding: 2px 6px;
	text-align: left;
	border-bottom: 1px solid var(--ql-border);
	vertical-align: top;
}

.rows-table th {
	color: var(--ql-text-muted);
	font-weight: 500;
}
</style>
