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
						<td v-for="col in columns" :key="col">{{ formatValue(row[col]) }}</td>
					</tr>
				</tbody>
			</table>
		</div>
		<div v-if="rows.length > MAX_ROWS" class="field-more">{{ __("+ {0} more", [rows.length - MAX_ROWS]) }}</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { __ } from "@/utils/i18n";
import { formatKey, formatValue } from "./helpers";

const props = defineProps({
	label: { type: String, required: true },
	rows: { type: Array, required: true },
});

const MAX_ROWS = 10;
const SKIPPED_COLUMNS = new Set(["name", "idx", "doctype", "parent", "parentfield", "parenttype"]);

const shownRows = computed(() => props.rows.slice(0, MAX_ROWS));

const columns = computed(() => {
	const seen = new Set();
	for (const row of shownRows.value) {
		for (const [key, value] of Object.entries(row)) {
			if (!SKIPPED_COLUMNS.has(key) && (value === null || typeof value !== "object")) seen.add(key);
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

.field-more {
	margin-top: 4px;
	color: var(--ql-text-muted);
}
</style>
