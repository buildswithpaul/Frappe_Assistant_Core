<template>
	<div v-if="hasDetails" class="approval-table">
		<template v-for="[key, value] in visibleRows" :key="key">
			<span class="field-key">{{ formatKey(key) }}</span>
			<span
				class="field-value"
				:class="{
					'value-mono': !isCondition(key) && isMonoValue(key, value),
					'value-money': !isCondition(key) && isMoneyKey(key),
				}"
			>
				<ConditionValue v-if="isCondition(key)" :expression="value" />
				<template v-else>{{ formatValue(value) }}</template>
			</span>
		</template>
		<template v-if="fieldSplit.overflowCount > 0">
			<span class="field-more">{{ __("+ {0} more", [fieldSplit.overflowCount]) }}</span>
			<button class="field-toggle" @click="showAllFields = !showAllFields">
				{{ showAllFields ? __("Show fewer fields ‹") : __("Show all fields ›") }}
			</button>
		</template>
		<template v-if="liveFields.length">
			<div class="goes-live" data-test="goes-live">{{ __("This goes live") }}</div>
			<p v-if="liveMissing" class="goes-live-missing" data-test="goes-live-missing">
				{{ __("Couldn't load the code that goes live. Check it in Desk before approving.") }}
			</p>
		</template>
		<CodePreview
			v-for="[key, value] in codeRows"
			:key="key"
			:label="formatKey(key)"
			:code="value"
			:language="codeLanguage(key, doctype)"
			:previous="previousCode(key)"
		/>
		<CodePreview
			v-for="[key, value] in storedLiveRows"
			:key="`live-${key}`"
			:label="formatKey(key)"
			:code="value"
			:language="codeLanguage(key, doctype)"
		/>
		<ChildTable v-for="[key, rows] in tableRows" :key="key" :label="key" :rows="rows" />
		<ApprovalNotes :block="block" />
	</div>
</template>

<script setup>
import { computed, ref } from "vue";
import { __ } from "@/utils/i18n";
import ApprovalNotes from "./ApprovalNotes.vue";
import ChildTable from "./ChildTable.vue";
import ConditionValue from "./ConditionValue.vue";
import CodePreview from "./CodePreview.vue";
import { goesLiveFields, renameKeys, writesCondition } from "./customisation";
import { useCurrentCode } from "./useCurrentCode";
import {
	flattenInput,
	formatKey,
	formatValue,
	isMonoValue,
	isMoneyKey,
	isCodeKey,
	isChildTable,
	codeLanguage,
	splitDetailFields,
} from "./helpers";

const props = defineProps({
	block: { type: Object, required: true },
});

const showAllFields = ref(false);
const { current: currentCode, failed: currentCodeFailed } = useCurrentCode(() => props.block);

// A rename the tool will not make is a notice (ApprovalNotes), never a changed field.
const flat = computed(() => {
	if (!props.block.input) return {};
	const hidden = renameKeys(props.block.tool_name, props.block.input);
	return Object.fromEntries(
		Object.entries(flattenInput(props.block.input)).filter(([key]) => !hidden.includes(key)),
	);
});
const hasDetails = computed(() => Object.keys(flat.value).length > 0);
const doctype = computed(() => flat.value.doctype);

// Code and child tables always show in full; only the plain fields fold behind "Show all fields".
const codeRows = computed(() =>
	Object.entries(flat.value).filter(([k, v]) => isCodeKey(k) && typeof v === "string" && v !== ""),
);
const tableRows = computed(() => Object.entries(flat.value).filter(([, v]) => isChildTable(v)));
const plainFields = computed(() =>
	Object.fromEntries(
		Object.entries(flat.value).filter(
			([k, v]) => !codeRows.value.some(([ck]) => ck === k) && !isChildTable(v),
		),
	),
);

const fieldSplit = computed(() => splitDetailFields(plainFields.value, 4));
const visibleRows = computed(() =>
	showAllFields.value ? [...fieldSplit.value.primary, ...fieldSplit.value.overflow] : fieldSplit.value.primary,
);

// Switching code on runs what is stored, so the card shows it, not just "Enabled 1".
const liveFields = computed(() => goesLiveFields(props.block.tool_name, props.block.input));
const unchangedLiveFields = computed(() =>
	liveFields.value.filter((key) => !codeRows.value.some(([ck]) => ck === key)),
);
const storedLiveRows = computed(() =>
	unchangedLiveFields.value
		.map((key) => [key, currentCode.value?.[key]])
		.filter(([, stored]) => typeof stored === "string" && stored !== ""),
);
const liveMissing = computed(
	() =>
		currentCodeFailed.value ||
		(currentCode.value !== null && unchangedLiveFields.value.some((key) => currentCode.value[key] === undefined)),
);

// A condition expression is read as a sentence; the raw text stays behind a toggle.
const isCondition = (key) => writesCondition(props.block.tool_name, props.block.input, key);

function previousCode(key) {
	const stored = currentCode.value?.[key];
	if (currentCode.value === null || stored === undefined) return null;
	return typeof stored === "string" ? stored : "";
}
</script>

<style scoped>
.approval-table {
	display: grid;
	grid-template-columns: auto 1fr;
	gap: 5px 14px;
	padding: 10px 14px;
	font-size: 11.5px;
}

.field-key {
	color: var(--ql-text-muted);
}

.field-value {
	color: var(--ql-text);
	font-weight: 500;
	word-break: break-word;
}

/* Tabular mono numerals/dates so values align on the decimal (spec §2.2) */
.value-mono {
	font-family: ui-monospace, "SF Mono", "Cascadia Code", monospace;
	font-variant-numeric: tabular-nums;
}

/* Gold reserved for money (spec §2.1) */
.value-money {
	color: var(--ql-gold);
}

.field-more {
	color: var(--ql-text-muted);
	align-self: start;
}

.goes-live {
	grid-column: 1 / -1;
	margin-top: 4px;
	font-weight: 600;
	color: var(--ql-warning);
}

.goes-live-missing {
	grid-column: 1 / -1;
	margin: 0;
	color: var(--ql-danger);
}

.field-toggle {
	justify-self: start;
	background: transparent;
	border: none;
	padding: 0;
	font-size: 11.5px;
	color: var(--ql-accent);
	cursor: pointer;
}

.field-toggle:hover {
	color: var(--ql-accent-hover);
}
</style>
