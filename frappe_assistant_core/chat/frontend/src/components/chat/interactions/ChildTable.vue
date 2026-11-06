<template>
	<div class="child-table-wrap">
		<div class="child-table-label">{{ formatKey(label) }}</div>
		<div class="child-table-scroll">
			<table class="child-table">
				<thead>
					<tr>
						<th v-for="col in columns" :key="col">{{ formatKey(col) }}</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="(row, i) in shownRows" :key="i">
						<td v-for="col in columns" :key="col">
							<LongValue v-if="isLongValue(row[col])" :value="row[col]" />
							<template v-else>{{ formatValue(row[col]) }}</template>
						</td>
					</tr>
				</tbody>
			</table>
		</div>
		<button
			v-if="rows.length > MAX_ROWS"
			type="button"
			class="child-rows-toggle"
			:aria-expanded="String(showAll)"
			@click="showAll = !showAll"
		>
			{{ showAll ? __("Show fewer rows ‹") : __("Show all {0} rows", [rows.length]) }}
		</button>
	</div>
</template>

<script setup>
import { computed, ref } from "vue";
import { __ } from "@/utils/i18n";
import LongValue from "./LongValue.vue";
import { formatKey, formatValue, isLongValue } from "./helpers";

const props = defineProps({
	label: { type: String, required: true },
	rows: { type: Array, required: true },
});

// The first rows show; the rest open on request, so every row can be seen before approving.
const MAX_ROWS = 10;
const SKIPPED_COLUMNS = new Set(["name", "idx", "doctype", "parent", "parentfield", "parenttype"]);

const showAll = ref(false);
const shownRows = computed(() => (showAll.value ? props.rows : props.rows.slice(0, MAX_ROWS)));

const columns = computed(() => {
	const seen = new Set();
	for (const row of props.rows) {
		for (const [key, value] of Object.entries(row)) {
			if (SKIPPED_COLUMNS.has(key)) continue;
			if (value === null || typeof value !== "object") seen.add(key);
		}
	}
	return [...seen];
});
</script>

<style scoped>
.child-table-wrap {
	grid-column: 1 / -1;
	min-width: 0;
}

.child-table-label {
	color: var(--ql-text-muted);
	margin-bottom: 4px;
}

.child-table-scroll {
	overflow-x: auto;
	border: 1px solid var(--ql-border);
	border-radius: 8px;
}

.child-table {
	width: 100%;
	border-collapse: collapse;
	font-size: 11px;
}

.child-table th,
.child-table td {
	padding: 4px 8px;
	text-align: left;
	border-bottom: 1px solid var(--ql-border);
}

.child-table th {
	color: var(--ql-text-muted);
	font-weight: 500;
}

.child-table tbody tr:last-child td {
	border-bottom: none;
}

.child-rows-toggle {
	margin-top: 4px;
	background: transparent;
	border: none;
	padding: 0;
	font-size: 11.5px;
	color: var(--ql-accent);
	cursor: pointer;
}

.child-rows-toggle:hover {
	color: var(--ql-accent-hover);
}
</style>
