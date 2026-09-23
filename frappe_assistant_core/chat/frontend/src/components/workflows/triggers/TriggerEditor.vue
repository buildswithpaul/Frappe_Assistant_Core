<template>
	<div class="editor">
		<div class="editor-header">
			<button class="back-btn" @click="$emit('cancel')">← Back</button>
			<h3 class="editor-title">
				{{ existing ? "Edit trigger" : "New trigger" }}
			</h3>
		</div>

		<div class="field-block">
			<label class="field-label">Title <span class="req">*</span></label>
			<input
				v-model="form.title"
				class="field-input"
				placeholder="e.g. Notify team when invoice submitted"
			/>
		</div>

		<div class="field-row">
			<div class="field-block grow">
				<label class="field-label">DocType <span class="req">*</span></label>
				<LinkPicker
					v-model="form.reference_doctype"
					:fetcher="fetchDoctypes"
					placeholder="Start typing — e.g. Sales Invoice"
					empty-text="No matching DocType"
					@change="onDocTypeChanged"
				/>
			</div>

			<div class="field-block">
				<label class="field-label">Event <span class="req">*</span></label>
				<select v-model="form.doctype_event" class="field-input">
					<option value="after_insert">after_insert</option>
					<option value="on_update">on_update</option>
					<option value="on_submit">on_submit</option>
					<option value="on_cancel">on_cancel</option>
					<option value="on_trash">on_trash</option>
				</select>
			</div>
		</div>

		<div v-if="form.doctype_event === 'on_update'" class="field-block">
			<label class="field-label">Only fire if these fields changed</label>
			<input
				v-model="form.changed_fields"
				class="field-input mono"
				placeholder="e.g. status, grand_total (comma-separated)"
			/>
			<p class="hint">
				Leave empty to fire on any update. Listed fields must be comma-separated.
			</p>
		</div>

		<div class="field-block">
			<label class="field-label">Filters</label>
			<p class="hint">
				All filters must match for the trigger to fire (AND). Evaluated locally before
				enqueueing.
			</p>
			<div class="filter-rows">
				<div v-for="(row, idx) in form.filters" :key="idx" class="filter-row">
					<div class="filter-row-picker">
						<LinkPicker
							v-model="row.fieldname"
							:options="fieldOptions"
							placeholder="fieldname"
							empty-text="No matching field"
						/>
					</div>
					<select v-model="row.operator" class="field-input narrow">
						<option value="=">=</option>
						<option value="!=">!=</option>
						<option value=">">&gt;</option>
						<option value="<">&lt;</option>
						<option value=">=">&gt;=</option>
						<option value="<=">&lt;=</option>
						<option value="in">in</option>
						<option value="not in">not in</option>
						<option value="is set">is set</option>
						<option value="is not set">is not set</option>
					</select>
					<input
						v-model="row.value"
						class="field-input"
						placeholder="value"
						:disabled="['is set', 'is not set'].includes(row.operator)"
					/>
					<button class="icon-btn danger" @click="removeFilter(idx)">×</button>
				</div>
			</div>
			<button class="action-btn small" @click="addFilter">+ Add filter</button>
		</div>

		<div class="field-block checkbox-field">
			<label class="checkbox-inline">
				<input v-model="form.enabled" type="checkbox" />
				<span>Enabled</span>
			</label>
		</div>

		<div class="editor-actions">
			<button class="action-btn" @click="$emit('cancel')">Cancel</button>
			<button class="action-btn primary" :disabled="!canSave" @click="save">
				{{ existing ? "Save changes" : "Create trigger" }}
			</button>
		</div>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import api from "@/api/client";
import LinkPicker from "./LinkPicker.vue";
import { logger } from "@/utils/logger";

const props = defineProps({
	workflowName: { type: String, required: true },
	/** AR Workflow docname — sent alongside the display name so the lookup
	    survives the trigger rebinding. */
	workflowId: { type: String, default: "" },
	workflowDisplayName: { type: String, default: "" },
	existing: { type: Object, default: null },
});

const emit = defineEmits(["save", "cancel"]);

const doctypeFields = ref([]);

// Remote fetcher for the DocType picker — searches server-side on every
// keystroke (debounced by LinkPicker). Returns at most 50 rows; the server
// reports the total count so the picker can show "… and N more".
async function fetchDoctypes(query) {
	try {
		const res = await api.workflows.triggers.listDoctypes(query || null, 50);
		const rows = res?.doctypes || [];
		return {
			options: rows.map((dt) => {
				const bits = [];
				if (dt.module) bits.push(dt.module);
				if (dt.app && dt.app !== "frappe") bits.push(dt.app);
				if (dt.custom) bits.push("Custom");
				return {
					value: dt.name,
					label: dt.name,
					description: bits.join(" · "),
				};
			}),
			hasMore: !!res?.has_more,
		};
	} catch (err) {
		logger.error("Failed to load DocType list", err);
		return { options: [], hasMore: false };
	}
}

const fieldOptions = computed(() =>
	doctypeFields.value.map((f) => ({
		value: f.fieldname,
		label: f.label || f.fieldname,
		description: `${f.fieldname} · ${f.fieldtype}`,
	}))
);

const form = reactive({
	title: "",
	reference_doctype: "",
	doctype_event: "after_insert",
	changed_fields: "",
	filters: [],
	enabled: true,
});

onMounted(async () => {
	if (props.existing) {
		form.title = props.existing.title;
		form.reference_doctype = props.existing.reference_doctype;
		form.doctype_event = props.existing.doctype_event;
		form.changed_fields = props.existing.changed_fields || "";
		form.enabled = !!props.existing.enabled;
		form.filters = []; // will load on DocType selection below

		if (form.reference_doctype) {
			await loadFields(form.reference_doctype);
		}
		// Fetch full trigger including filters
		try {
			const detail = await api.workflows.triggers.list(
				props.workflowName,
				props.workflowId
			);
			const found = (detail?.triggers || []).find((t) => t.name === props.existing.name);
			if (found && found.filters) {
				form.filters = found.filters.map((r) => ({
					fieldname: r.fieldname,
					operator: r.operator,
					value: r.value || "",
				}));
			}
		} catch {
			/* ignore */
		}
	}
});

watch(
	() => form.doctype_event,
	(ev) => {
		if (ev !== "on_update") {
			form.changed_fields = "";
		}
	}
);

// Load fields only when the user PICKS a DocType from the dropdown (or clears
// it). Do NOT load on every keystroke — that triggers a storm of 417s from the
// server for partial / invalid names (e.g. "AR m", "AR mo", "AR model…").
async function onDocTypeChanged(opt) {
	if (opt && opt.value) {
		await loadFields(opt.value);
	} else {
		doctypeFields.value = [];
	}
}

async function loadFields(doctype) {
	try {
		const res = await api.workflows.triggers.getDoctypeFields(doctype);
		doctypeFields.value = res?.fields || [];
	} catch (err) {
		logger.error("Failed to load DocType fields", err);
		doctypeFields.value = [];
	}
}

function addFilter() {
	form.filters.push({ fieldname: "", operator: "=", value: "" });
}

function removeFilter(idx) {
	form.filters.splice(idx, 1);
}

const canSave = computed(
	() => form.title.trim() && form.reference_doctype.trim() && form.doctype_event
);

function save() {
	if (!canSave.value) return;

	const cleanedFilters = form.filters
		.filter((r) => r.fieldname.trim())
		.map((r) => ({
			fieldname: r.fieldname.trim(),
			operator: r.operator,
			value: ["is set", "is not set"].includes(r.operator) ? "" : r.value,
		}));

	emit("save", {
		title: form.title.trim(),
		reference_doctype: form.reference_doctype.trim(),
		doctype_event: form.doctype_event,
		changed_fields: form.changed_fields.trim(),
		filters: JSON.stringify(cleanedFilters),
		enabled: form.enabled ? 1 : 0,
	});
}
</script>

<style scoped>
.editor {
	display: flex;
	flex-direction: column;
	gap: 1rem;
	color: var(--ql-text);
}
.editor-header {
	display: flex;
	align-items: center;
	gap: 0.75rem;
}
.back-btn {
	background: none;
	border: none;
	color: var(--ql-accent);
	cursor: pointer;
	font-size: 0.8125rem;
	padding: 0;
}
.back-btn:hover {
	color: var(--ql-accent-hover);
}
.editor-title {
	margin: 0;
	font-size: 1rem;
	font-weight: 600;
	color: var(--ql-text);
}
.field-block {
	display: flex;
	flex-direction: column;
	gap: 0.25rem;
}
.field-row {
	display: flex;
	gap: 0.75rem;
}
.field-row .grow {
	flex: 1;
}
.field-label {
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-text);
}
.req {
	color: var(--ql-danger);
}
.field-input {
	padding: 0.5rem 0.625rem;
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	font-size: 0.8125rem;
	background: var(--ql-surface);
	color: var(--ql-text);
	outline: none;
	transition: border-color 0.15s ease;
}
.field-input:focus {
	border-color: var(--ql-accent);
}
.field-input:disabled {
	opacity: 0.6;
	cursor: not-allowed;
}
.field-input.narrow {
	flex: 0 0 6.875rem;
}
.field-input.mono {
	font-family: "SF Mono", Monaco, monospace;
}
.hint {
	margin: 0;
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	line-height: 1.4;
}
.filter-rows {
	display: flex;
	flex-direction: column;
	gap: 0.375rem;
	margin-bottom: 0.5rem;
}
.filter-row {
	display: flex;
	gap: 0.375rem;
	align-items: center;
}
.filter-row .field-input {
	flex: 1;
}
.filter-row-picker {
	flex: 1;
	min-width: 0;
}
.icon-btn {
	padding: 0.25rem 0.625rem;
	border: 1px solid var(--ql-border);
	background: var(--ql-surface);
	color: var(--ql-text);
	border-radius: 0.25rem;
	cursor: pointer;
	font-size: 0.8125rem;
	transition: background 0.15s ease;
}
.icon-btn:hover {
	background: var(--ql-subtle);
}
.icon-btn.danger {
	color: var(--ql-danger);
	border-color: color-mix(in srgb, var(--ql-danger) 40%, transparent);
}
.icon-btn.danger:hover {
	background: color-mix(in srgb, var(--ql-danger) 12%, transparent);
}
.action-btn {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.5rem 0.875rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
	background: var(--ql-subtle);
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
}
.action-btn:hover {
	background-color: var(--ql-border);
}
.action-btn.small {
	padding: 0.25rem 0.625rem;
	font-size: 0.75rem;
	align-self: flex-start;
}
.action-btn.primary {
	background: var(--ql-accent);
	color: white;
}
.action-btn.primary:hover {
	background: var(--ql-accent-hover);
}
.action-btn.primary:disabled {
	opacity: 0.5;
	cursor: not-allowed;
}
.checkbox-inline {
	display: flex;
	align-items: center;
	gap: 0.375rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
	cursor: pointer;
}
.checkbox-inline input[type="checkbox"] {
	accent-color: var(--ql-accent);
}
.editor-actions {
	display: flex;
	justify-content: flex-end;
	gap: 0.5rem;
	margin-top: 0.5rem;
}
</style>
