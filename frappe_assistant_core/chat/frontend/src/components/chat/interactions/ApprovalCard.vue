<template>
	<div class="approval-card" :class="{ 'card-decided': hasDecision }">
		<!-- Gold-tinted header band -->
		<div class="approval-header">
			<div class="approval-icon-tile">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="1.8"
						d="M12 4v16m8-8H4"
					/>
				</svg>
			</div>
			<div class="approval-heading">
				<div class="approval-title">Approve: {{ approvalTitle }}</div>
				<div v-if="consequence" class="approval-subtitle">{{ consequence }}</div>
			</div>
			<span v-if="!hasDecision" class="needs-you-pill">NEEDS YOU</span>
		</div>

		<p v-if="toolDescription" class="approval-description">{{ toolDescription }}</p>

		<!-- Scannable 2-col key/value table -->
		<div v-if="hasDetails" class="approval-table">
			<template v-for="[key, value] in visibleRows" :key="key">
				<span class="field-key">{{ formatKey(key) }}</span>
				<span
					class="field-value"
					:class="{ 'value-mono': isMonoValue(key, value), 'value-money': isMoneyKey(key) }"
					>{{ formatValue(value) }}</span
				>
			</template>
			<template v-if="fieldSplit.overflowCount > 0">
				<span class="field-more">+ {{ fieldSplit.overflowCount }} more</span>
				<button class="field-toggle" @click="showAllFields = !showAllFields">
					{{ showAllFields ? "Show fewer fields ‹" : "Show all fields ›" }}
				</button>
			</template>
		</div>

		<div v-if="hasDecision" class="decided-banner">
			<span class="decided-label">{{ decidedLabel }}</span>
			<span v-if="batchInfo" class="decided-batch">{{ batchInfo }}</span>
		</div>

		<div v-else class="approval-actions">
			<button class="ql-btn ql-btn-approve" :disabled="submitting" @click="handleApprove('approve')">
				Approve
			</button>
			<button class="ql-btn ql-btn-reject" :disabled="submitting" @click="handleReject">
				Reject
			</button>
			<button class="ql-btn ql-btn-trust" :disabled="submitting" @click="handleApprove('trust')">
				Always allow this tool
			</button>
		</div>
	</div>
</template>

<script setup>
import { computed, ref } from "vue";
import {
	flattenInput,
	formatToolName,
	formatKey,
	formatValue,
	isMonoValue,
	isMoneyKey,
	splitDetailFields,
} from "./helpers";

const props = defineProps({
	block: { type: Object, required: true },
	submitting: { type: Boolean, default: false },
	batchInfo: { type: String, default: null },
});
const emit = defineEmits(["approve", "reject"]);

const hasDecision = computed(() => Boolean(props.block.decision));

const decidedLabel = computed(() => {
	const r = props.block.decision?.resolution;
	if (r === "approved") return "Approve";
	if (r === "trusted") return "Always allow";
	if (r === "rejected") return "Reject";
	return "Decided";
});

const approvalTitle = computed(() => {
	const map = {
		create_document: "Create Document",
		update_document: "Update Document",
		delete_document: "Delete Document",
		submit_document: "Submit Document",
	};
	return map[props.block.tool_name] || formatToolName(props.block.tool_name);
});

const hasDetails = computed(
	() => props.block.input && Object.keys(flattenInput(props.block.input)).length > 0,
);

const showAllFields = ref(false);

const fieldSplit = computed(() => {
	if (!props.block.input) return { primary: [], overflow: [], overflowCount: 0 };
	return splitDetailFields(flattenInput(props.block.input), 4);
});

// Consequence subtitle — states the concrete write effect, but ONLY for tools
// we can be certain write to the ERP. Showing "This action will write to your
// ERP" for every other tool was misleading: read-only/clarification tools (e.g.
// ask_user, get_skill) and dynamic tools (run_python_code) don't necessarily
// write, and a false "will write" warning erodes trust and trains users to
// ignore it on calls that genuinely do mutate data. For unmapped tools we show
// no consequence line — the title, tool description and input table already
// convey what is about to happen.
const consequence = computed(() => {
	const map = {
		create_document: "This will write a new record to your ERP",
		update_document: "This will modify an existing record in your ERP",
		delete_document: "This will permanently delete a record from your ERP",
		submit_document: "This will submit a record — it becomes immutable",
	};
	return map[props.block.tool_name] || "";
});

const visibleRows = computed(() =>
	showAllFields.value
		? [...fieldSplit.value.primary, ...fieldSplit.value.overflow]
		: fieldSplit.value.primary,
);

// First sentence of the full MCP tool description so the user sees *what
// this tool does* before approving. Falls back to null if unavailable.
const toolDescription = computed(() => {
	const d = props.block.toolDescription || props.block.tool_description;
	if (!d) return null;
	const cleaned = String(d).replace(/\s+/g, " ").trim();
	const firstStop = cleaned.search(/[.!?]\s/);
	if (firstStop > 0 && firstStop < 200) return cleaned.slice(0, firstStop + 1);
	return cleaned.length > 140 ? cleaned.slice(0, 140) + "…" : cleaned;
});

function handleApprove(trustLevel) {
	const responses = (props.block.interrupts || []).map((i) => ({
		interruptId: i.id,
		response: trustLevel,
	}));
	emit("approve", props.block.id, responses);
}

function handleReject() {
	const responses = (props.block.interrupts || []).map((i) => ({
		interruptId: i.id,
		response: "rejected",
	}));
	emit("reject", props.block.id, responses);
}
</script>

<style scoped>
.approval-card {
	margin: 8px 0;
	border-radius: 12px;
	border: 1px solid var(--ql-gold-soft);
	background: var(--ql-surface);
	overflow: hidden;
}

/* Gold-tinted header band */
.approval-header {
	display: flex;
	align-items: center;
	gap: 10px;
	padding: 11px 14px;
	background: var(--ql-gold-soft);
	border-bottom: 1px solid var(--ql-gold-soft);
}

.approval-icon-tile {
	flex-shrink: 0;
	width: 30px;
	height: 30px;
	border-radius: 8px;
	background: var(--ql-gold);
	color: #fff;
	display: flex;
	align-items: center;
	justify-content: center;
}

.approval-icon-tile svg {
	width: 16px;
	height: 16px;
}

.approval-heading {
	flex: 1;
	min-width: 0;
}

.approval-title {
	font-size: 13px;
	font-weight: 600;
	color: var(--ql-text);
	line-height: 1.3;
}

.approval-subtitle {
	font-size: 11px;
	color: var(--ql-text-muted);
	margin-top: 2px;
}

.needs-you-pill {
	flex-shrink: 0;
	font-size: 10px;
	font-weight: 600;
	letter-spacing: 0.02em;
	color: var(--ql-warning);
	background: var(--ql-gold-soft);
	padding: 3px 8px;
	border-radius: 20px;
}

.approval-description {
	margin: 0;
	padding: 8px 14px 0;
	font-size: 12px;
	color: var(--ql-text-secondary);
	line-height: 1.45;
}

/* Scannable 2-col key/value table */
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

/* Decided banner (post-click, pre-resume) */
.decided-banner {
	display: flex;
	align-items: center;
	gap: 8px;
	padding: 8px 14px 10px;
	font-size: 12px;
}

.decided-label {
	font-weight: 600;
	color: var(--ql-accent);
}

.decided-batch {
	color: var(--ql-text-muted);
	font-style: italic;
}

.card-decided {
	opacity: 0.75;
}

/* Action row — Approve filled, Reject quiet, Always-allow pushed right */
.approval-actions {
	display: flex;
	align-items: center;
	gap: 8px;
	padding: 4px 14px 12px;
}

.ql-btn {
	font-size: 12px;
	font-weight: 500;
	border-radius: 8px;
	cursor: pointer;
	transition: all 0.15s ease;
	white-space: nowrap;
}

.ql-btn:disabled {
	opacity: 0.4;
	cursor: not-allowed;
}

.ql-btn-approve {
	font-weight: 600;
	padding: 7px 16px;
	background: var(--ql-accent);
	color: #fff;
	border: none;
}

.ql-btn-approve:hover:not(:disabled) {
	background: var(--ql-accent-hover);
}

.ql-btn-reject {
	padding: 7px 14px;
	background: var(--ql-surface);
	color: var(--ql-text-secondary);
	border: 1px solid var(--ql-border);
}

.ql-btn-reject:hover:not(:disabled) {
	color: var(--ql-danger);
	border-color: var(--ql-danger);
}

.ql-btn-trust {
	margin-left: auto;
	padding: 7px 14px;
	background: transparent;
	color: var(--ql-text-muted);
	border: none;
}

.ql-btn-trust:hover:not(:disabled) {
	color: var(--ql-text-secondary);
}
</style>
