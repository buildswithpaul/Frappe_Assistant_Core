<template>
	<div class="record-table">
		<div class="record-scroll" role="region" tabindex="0" :aria-label="__('Records')">
			<table>
				<thead>
					<tr>
						<th v-for="column in view.columns" :key="column.key" scope="col">{{ column.label }}</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="(row, i) in shown" :key="i">
						<td v-for="column in view.columns" :key="column.key" :title="cellText(row, column.key)">
							{{ cellText(row, column.key) }}
						</td>
					</tr>
				</tbody>
			</table>
		</div>
		<div class="record-note">
			<span>{{ note }}</span>
			<button v-if="view.rows.length > PREVIEW_ROWS" type="button" class="record-toggle" :aria-expanded="showAll" @click="showAll = !showAll">
				{{ showAll ? __("Show fewer") : __("Show all {0}", [view.rows.length]) }}
			</button>
		</div>
	</div>
</template>

<script setup>
import { computed, ref } from "vue";
import { __ } from "@/utils/i18n";
import { cellText } from "./toolView";

const PREVIEW_ROWS = 5;

const props = defineProps({
	// A `table` view from toolView: columns, rows, total and hiddenColumns, and `returned` for a preview.
	view: { type: Object, required: true },
	// False where no Raw tab sits beside the table (a script's step), so the note does not point at one.
	hasRaw: { type: Boolean, default: true },
});

const showAll = ref(false);
const shown = computed(() => (showAll.value ? props.view.rows : props.view.rows.slice(0, PREVIEW_ROWS)));

const note = computed(() => {
	const { rows, total, returned, hiddenColumns } = props.view;
	const parts = [];
	// A script's step shows a preview of what the call returned, which may itself be a part of what matched.
	if (returned > rows.length) {
		parts.push(__("First {0} of {1}.", [rows.length, returned]));
		if (total > returned) parts.push(__("{0} matched.", [total]));
	} else if (total > rows.length) parts.push(__("{0} of {1} returned.", [rows.length, total]));
	else if (rows.length > PREVIEW_ROWS && !showAll.value) parts.push(__("First {0} of {1}.", [PREVIEW_ROWS, rows.length]));
	else parts.push(rows.length === 1 ? __("1 record.") : __("All {0} shown.", [rows.length]));
	if (hiddenColumns && props.hasRaw) parts.push(hiddenColumns === 1 ? __("1 more column in Raw.") : __("{0} more columns in Raw.", [hiddenColumns]));
	else if (hiddenColumns) parts.push(hiddenColumns === 1 ? __("1 more column.") : __("{0} more columns.", [hiddenColumns]));
	return parts.join(" ");
});
</script>

<style scoped>
.record-table {
	min-width: 0;
}
.record-scroll {
	overflow-x: auto;
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-md, 8px);
}
.record-scroll:focus-visible {
	outline: 2px solid var(--ql-accent);
	outline-offset: 1px;
}
table {
	width: 100%;
	border-collapse: collapse;
	font-size: 12px;
	font-variant-numeric: tabular-nums;
}
th {
	padding: 5px 10px;
	text-align: left;
	font-weight: 500;
	white-space: nowrap;
	color: var(--ql-text-muted);
	background: var(--ql-subtle);
}
td {
	max-width: 280px;
	padding: 5px 10px;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
	color: var(--ql-text);
	border-top: 1px solid var(--ql-border);
}
.record-note {
	display: flex;
	flex-wrap: wrap;
	gap: 4px 10px;
	margin-top: 5px;
	font-size: 11px;
	color: var(--ql-text-muted);
}
.record-toggle {
	padding: 0;
	font: inherit;
	color: var(--ql-accent);
	background: transparent;
	border: none;
	cursor: pointer;
}
.record-toggle:hover {
	color: var(--ql-accent-hover);
}
.record-toggle:focus-visible {
	outline: 2px solid var(--ql-accent);
	outline-offset: 2px;
}
</style>
