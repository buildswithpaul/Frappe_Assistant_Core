<template>
	<div v-if="hasContent" class="approval-details">
		<section v-if="liveFields.length" class="goes-live-box">
			<h4 class="goes-live" data-test="goes-live">{{ __("This goes live") }}</h4>
			<div v-if="audience" class="goes-live-audience" data-test="goes-live-audience">
				<span class="goes-live-label">{{ __("Goes live to") }}</span>
				<span v-for="role in audience.roles" :key="role" class="role-chip">{{ role }}</span>
			</div>
			<div v-if="audience?.everyone" class="goes-live-missing" data-test="goes-live-everyone">
				{{ __("All and Guest include every user who can log in.") }}
			</div>
			<div v-if="codeLoading" class="goes-live-note" data-test="goes-live-loading">
				{{ __("Loading the code that goes live…") }}
			</div>
			<div v-else-if="liveEmpty" class="goes-live-note" data-test="goes-live-empty">{{ __("(empty)") }}</div>
			<div v-if="liveMissing" class="goes-live-missing" data-test="goes-live-missing">
				{{ __("Couldn't load the code that goes live. Check it in Desk before approving.") }}
			</div>
		</section>
		<div v-if="visibleRows.length" class="approval-table">
			<template v-for="[key, value] in visibleRows" :key="key">
				<span class="field-key">{{ formatKey(key) }}</span>
				<span
					class="field-value"
					:class="{
						'value-num': !isCondition(key) && isMonoValue(key, value),
						'value-money': !isCondition(key) && isMoneyKey(key),
					}"
				>
					<ConditionValue v-if="isCondition(key)" :expression="value" />
					<template v-else>{{ displayValue(key, value) }}</template>
				</span>
			</template>
			<template v-if="fieldSplit.overflowCount > 0">
				<span class="field-more">{{ __("+ {0} more", [fieldSplit.overflowCount]) }}</span>
				<button type="button" class="field-toggle" @click="showAllFields = !showAllFields">
					{{ showAllFields ? __("Show fewer fields") : __("Show all fields") }}
				</button>
			</template>
		</div>
		<div v-if="codeRows.length || storedLiveRows.length" class="code-stack">
			<CodePreview
				v-for="[key, value] in codeRows"
				:key="key"
				:label="codeLabel(key, value)"
				:code="value"
				:language="codeLanguage(key, doctype, flat)"
				:previous="previousCode(key)"
			/>
			<CodePreview
				v-for="[key, value] in storedLiveRows"
				:key="`live-${key}`"
				:label="formatKey(key)"
				:code="value"
				:language="codeLanguage(key, doctype, flat)"
			/>
		</div>
		<ChildTable
			v-for="[key, rows] in tableRows"
			:key="key"
			:label="key"
			:rows="rows"
		/>
		<div v-if="rowCode.length" class="code-stack">
			<CodePreview
				v-for="cell in rowCode"
				:key="cell.key"
				:label="cell.label"
				:code="cell.code"
				:language="cell.language"
				:previous="cell.previous"
			/>
		</div>
		<ApprovalNotes :block="block" />
	</div>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { __ } from "@/utils/i18n";
import ApprovalNotes from "./ApprovalNotes.vue";
import ChildTable from "./ChildTable.vue";
import ConditionValue from "./ConditionValue.vue";
import CodePreview from "./CodePreview.vue";
import { baseToolName } from "@/utils/toolNames";
import { headlineKeys } from "./approvalHeadline";
import { describeCondition } from "./conditions";
import { goesLiveAudience, goesLiveFields, renameKeys, writesCondition } from "./customisation";
import { useCurrentCode } from "./useCurrentCode";
import {
	displayValue,
	flattenInput,
	formatKey,
	isMonoValue,
	isMoneyKey,
	isCodeField,
	isChildTable,
	isEvalExpression,
	codeLanguage,
	splitDetailFields,
} from "./helpers";
import { rowCodeCells, rowsWithoutCode } from "./rowCode";

const props = defineProps({
	block: { type: Object, required: true },
});
// True while the code that goes live is loading: the card must not be approved unseen.
const emit = defineEmits(["blocking"]);

const showAllFields = ref(false);
const {
	current: currentCode,
	failed: currentCodeFailed,
	loading: codeLoading,
} = useCurrentCode(() => props.block);
watch(codeLoading, (loading) => emit("blocking", loading), { immediate: true });

// A rename the tool will not make is a notice (ApprovalNotes), never a changed field.
const flat = computed(() => {
	if (!props.block.input) return {};
	const hidden = renameKeys(props.block.tool_name, props.block.input);
	return Object.fromEntries(
		Object.entries(flattenInput(props.block.input)).filter(([key]) => !hidden.includes(key)),
	);
});
const hasContent = computed(() => Object.keys(flat.value).length > 0 || liveFields.value.length > 0);
const doctype = computed(() => flat.value.doctype);

// Code and child tables always show in full; only the plain fields fold behind "Show all fields".
const codeRows = computed(() =>
	Object.entries(flat.value).filter(
		([k, v]) => isCodeField(k, doctype.value, flat.value) && typeof v === "string" && v !== "",
	),
);
// Code in child rows (a transition's condition, a field's eval: condition) shows in full below its
// table, diffed against the stored row on an update, and not in the table.
const rowCode = computed(() => rowCodeCells(doctype.value, flat.value, currentCode.value));
const tableRows = computed(() =>
	Object.entries(flat.value)
		.filter(([, v]) => isChildTable(v))
		.map(([key, rows]) => [key, rowsWithoutCode(doctype.value, key, rows, rowCode.value)]),
);

// An eval: condition keeps its plain reading beside the field name, above the code itself.
function codeLabel(key, value) {
	return isEvalExpression(value) ? `${formatKey(key)}: ${describeCondition(value)}` : formatKey(key);
}
// The title already names the record and its doctype, so the field list starts at what changes.
const shownInTitle = computed(() => headlineKeys(props.block));
// A blank value is a change only on an update (it clears the field); elsewhere it is noise.
const keepsBlanks = computed(() => baseToolName(props.block.tool_name) === "update_document");
const isBlank = (v) => v === null || v === undefined || v === "";
const plainFields = computed(() =>
	Object.fromEntries(
		Object.entries(flat.value).filter(
			([k, v]) =>
				!codeRows.value.some(([ck]) => ck === k) &&
				!isChildTable(v) &&
				!shownInTitle.value.includes(k) &&
				(keepsBlanks.value || !isBlank(v)),
		),
	),
);

const fieldSplit = computed(() => splitDetailFields(plainFields.value, 4));
const visibleRows = computed(() =>
	showAllFields.value ? [...fieldSplit.value.primary, ...fieldSplit.value.overflow] : fieldSplit.value.primary,
);

// Switching code on runs what is stored, so the card shows it, not just "Enabled 1".
const liveFields = computed(() => goesLiveFields(props.block.tool_name, props.block.input));
// A go-live field the update also writes shows its new value (diff or table row) instead.
const unchangedLiveFields = computed(() => liveFields.value.filter((key) => !(key in flat.value)));
const storedLiveRows = computed(() =>
	unchangedLiveFields.value
		.map((key) => [key, currentCode.value?.[key]])
		.filter(([, stored]) => typeof stored === "string" && stored !== ""),
);
// A FAC Page's stored roles; an update that sets roles shows them as a changed child table.
const audience = computed(() =>
	unchangedLiveFields.value.includes("roles") ? goesLiveAudience(currentCode.value?.roles) : null,
);
// roles is an audience, not code: an empty list must not hide "(empty)" for empty code.
const unchangedLiveCode = computed(() => unchangedLiveFields.value.filter((key) => key !== "roles"));
const liveEmpty = computed(
	() =>
		currentCode.value !== null &&
		unchangedLiveCode.value.length > 0 &&
		unchangedLiveCode.value.every((key) => currentCode.value[key] === ""),
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
.approval-details {
	display: flex;
	flex-direction: column;
	gap: 12px;
	padding: 0 16px 12px;
	font-size: 13px;
}

.goes-live-box {
	display: flex;
	flex-direction: column;
	gap: 6px;
	padding: 10px 12px;
	border-radius: var(--ql-radius-md, 8px);
	background: var(--ql-gold-soft);
}

.goes-live {
	margin: 0;
	font-size: 13px;
	font-weight: 600;
	color: var(--ql-text);
}

.goes-live-audience {
	display: flex;
	flex-wrap: wrap;
	align-items: center;
	gap: 6px;
	margin: 0;
}

.goes-live-label {
	color: var(--ql-text-secondary);
	margin-right: 2px;
}

.role-chip {
	padding: 2px 8px;
	border-radius: 999px;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border-hover);
	font-size: 12px;
	font-weight: 500;
	color: var(--ql-text);
}

.goes-live-note {
	margin: 0;
	color: var(--ql-text-secondary);
}

.goes-live-missing {
	margin: 0;
	color: var(--ql-danger);
}

.approval-table {
	display: grid;
	grid-template-columns: minmax(96px, max-content) 1fr;
	gap: 6px 16px;
}

.field-key {
	color: var(--ql-text-muted);
}

.field-value {
	color: var(--ql-text);
	font-weight: 500;
	overflow-wrap: anywhere;
}

/* Figures align on the digit without switching typeface. */
.value-num {
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

.field-toggle {
	justify-self: start;
	background: transparent;
	border: none;
	padding: 0;
	font: inherit;
	color: var(--ql-accent);
	cursor: pointer;
}

.field-toggle:hover {
	color: var(--ql-accent-hover);
}

.field-toggle:focus-visible {
	outline: 2px solid var(--ql-accent);
	outline-offset: 2px;
	border-radius: 4px;
}

.code-stack {
	display: flex;
	flex-direction: column;
	gap: 8px;
}

@container (max-width: 380px) {
	.approval-table {
		grid-template-columns: 1fr;
		gap: 2px;
	}

	.field-value {
		margin-bottom: 6px;
	}
}
</style>
