<template>
	<div class="pwf" :class="field.status && `is-${field.status}`">
		<dt class="pwf-name">{{ field.name }}</dt>
		<dd class="pwf-value">
			<span v-if="field.status === 'blanked'" class="pwf-flag">{{ __("will be cleared") }}</span>
			<span v-else-if="field.status === 'emptied'" class="pwf-flag">
				{{ __("all {0} rows will be removed", [field.beforeRows]) }}
			</span>
			<template v-else-if="field.rows">
				<span v-if="field.beforeRows !== undefined" class="pwf-before">
					{{ __("{0} rows now", [field.beforeRows]) }} →
				</span>
				<ol class="pwf-rows">
					<li v-for="(row, i) in field.rows" :key="i">
						<span v-for="(cell, j) in row" :key="j" class="pwf-cell">
							<span class="pwf-cell-name">{{ cell.name }}</span> {{ cell.value }}
						</span>
					</li>
				</ol>
				<span v-if="!field.rows.length" class="pwf-flag">{{ __("no rows") }}</span>
			</template>
			<template v-else>
				<span v-if="field.before !== undefined && field.status === 'changed'" class="pwf-before">
					<PageWriteText :text="field.before" /> →
				</span>
				<PageWriteText :text="field.value" />
			</template>
			<span v-if="field.status === 'blanked' && field.before" class="pwf-before">
				({{ __("now") }} <PageWriteText :text="field.before" />)</span
			>
		</dd>
	</div>
</template>

<script setup>
import { __ } from "@/utils/i18n";

import PageWriteText from "./PageWriteText.vue";

defineProps({
	// From describePageRequest: {name, value, before?, beforeRows?, status?, rows?}.
	field: { type: Object, required: true },
});
</script>

<style scoped>
.pwf {
	display: contents;
}
.pwf-name {
	color: var(--ql-text-muted);
	overflow-wrap: anywhere;
}
.pwf-value {
	margin: 0;
	color: var(--ql-text);
	overflow-wrap: anywhere;
	white-space: pre-wrap;
}
.pwf-before {
	color: var(--ql-text-muted);
}
.pwf-flag {
	font-weight: 600;
	color: var(--ql-danger);
}
.pwf-rows {
	margin: 0;
	padding-left: 18px;
}
.pwf-cell {
	margin-right: 10px;
}
.pwf-cell-name {
	color: var(--ql-text-muted);
}
</style>
