<template>
	<div class="approval-records" data-test="records">
		<div class="records-bar">
			<span class="records-heading" data-test="records-heading">{{ heading }}</span>
			<button
				type="button"
				class="records-toggle"
				:aria-expanded="String(expanded)"
				:aria-controls="scrollId"
				@click="expanded = !expanded"
			>
				{{ expanded ? __("Collapse") : __("Expand") }}
			</button>
		</div>
		<!-- Every record is here; the height is bounded so Approve and Reject stay near them -->
		<div
			:id="scrollId"
			class="records-scroll"
			data-test="records-scroll"
			role="region"
			tabindex="0"
			:aria-label="heading"
			:style="expanded ? null : { maxHeight: `${MAX_HEIGHT}px` }"
		>
			<table v-for="table in tables" :key="table.doctype" class="records-table">
				<caption>{{ table.doctype }} ({{ table.rows.length }})</caption>
				<thead>
					<tr>
						<th v-for="key in table.columns" :key="key" scope="col">{{ columnLabel(key) }}</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="(row, i) in table.rows" :key="i">
						<td
							v-for="key in table.columns"
							:key="key"
							:class="{ 'value-mono': key in row && isMonoValue(key, row[key]) }"
						>
							<template v-if="key in row">
								<span v-if="tableReplacement(toolName, row[key])" class="table-replaced">
									{{ tableReplacement(toolName, row[key]) }}
								</span>
								<RowsToggle v-if="isChildTable(row[key])" :rows="row[key]" />
								<LongValue v-else-if="isLongValue(row[key])" :value="row[key]" :code="isCodeKey(key)" />
								<template v-else-if="!tableReplacement(toolName, row[key])">{{ cellText(row[key]) }}</template>
							</template>
						</td>
					</tr>
				</tbody>
			</table>
		</div>
	</div>
</template>

<script setup>
// Several records in one call: one table per doctype, every record and every key it sends,
// so the user sees exactly what they approve. A key a record doesn't send is an empty cell.
import { computed, ref, useId } from "vue";
import { __ } from "@/utils/i18n";
import LongValue from "./LongValue.vue";
import RowsToggle from "./RowsToggle.vue";
import {
	cellText,
	columnLabel,
	documentTables,
	documentsHeading,
	isChildTable,
	tableReplacement,
	isCodeKey,
	isLongValue,
	isMonoValue,
} from "./helpers";

const props = defineProps({
	input: { type: Object, required: true },
	toolName: { type: String, default: "" },
});

const MAX_HEIGHT = 320;
const expanded = ref(false);
const scrollId = useId();
const tables = computed(() => documentTables(props.input));
const heading = computed(() => documentsHeading(props.toolName, props.input));
</script>

<style scoped>
.table-replaced {
	display: block;
	color: var(--ql-danger);
	font-weight: 600;
}

.approval-records {
	padding: 10px 14px 0;
	font-size: 11.5px;
}

.records-bar {
	display: flex;
	align-items: baseline;
	justify-content: space-between;
	gap: 8px;
	margin-bottom: 6px;
}

.records-heading {
	color: var(--ql-text);
	font-weight: 600;
}

.records-toggle {
	flex-shrink: 0;
	background: transparent;
	border: none;
	padding: 0;
	font-size: 11.5px;
	color: var(--ql-accent);
	cursor: pointer;
}

.records-toggle:hover {
	color: var(--ql-accent-hover);
}

.records-scroll {
	overflow: auto;
	border: 1px solid var(--ql-border);
	border-radius: 8px;
	margin-bottom: 6px;
}

.records-scroll:focus-visible {
	outline: 2px solid var(--ql-accent);
	outline-offset: 1px;
}

.records-table {
	width: 100%;
	border-collapse: collapse;
	font-size: 11px;
}

.records-table + .records-table {
	border-top: 1px solid var(--ql-border);
}

.records-table caption {
	caption-side: top;
	text-align: left;
	padding: 6px 8px 2px;
	color: var(--ql-text-muted);
	font-weight: 600;
}

.records-table th,
.records-table td {
	padding: 4px 8px;
	text-align: left;
	vertical-align: top;
	border-bottom: 1px solid var(--ql-border);
	white-space: nowrap;
}

.records-table td {
	color: var(--ql-text);
}

.records-table th {
	position: sticky;
	top: 0;
	background: var(--ql-surface);
	color: var(--ql-text-muted);
	font-weight: 500;
}

.records-table tbody tr:last-child td {
	border-bottom: none;
}

/* Tabular mono numerals/dates so values align on the decimal (spec §2.2) */
.value-mono {
	font-family: ui-monospace, "SF Mono", "Cascadia Code", monospace;
	font-variant-numeric: tabular-nums;
}
</style>
