<template>
	<div v-if="review && review.ready" class="mapping-review">
		<div class="mr-head">
			<span class="mr-title">{{ __("Columns of {0} → {1}", [review.file_name || session, review.doctype]) }}</span>
			<span v-if="saving" class="mr-saving">{{ __("Saving…") }}</span>
		</div>

		<div v-if="review.missing_required.length" class="mr-missing" role="alert">
			<strong>{{ __("Required, with no column:") }}</strong>
			<span v-for="field in review.missing_required" :key="field.field" class="mr-missing-field">
				{{ field.table ? field.table + ": " + field.label : field.label }}
			</span>
			<div class="mr-hint">{{ __("Pick a column for each below, or add the column to your file and send it again.") }}</div>
		</div>
		<div v-if="!review.editable && review.refused" class="mr-locked">{{ review.refused }}</div>
		<div v-if="error" class="mr-error" role="alert">{{ error }}</div>

		<div class="mr-table" role="table" :aria-label="__('Column mapping')">
			<div class="mr-row mr-header" role="row">
				<span role="columnheader">{{ __("Your column") }}</span>
				<span role="columnheader">{{ __("First values") }}</span>
				<span role="columnheader">{{ __("ERPNext field") }}</span>
				<span role="columnheader">{{ __("Status") }}</span>
			</div>
			<div v-for="col in review.columns" :key="col.position" class="mr-row" role="row">
				<span class="mr-column" role="cell" :data-label="__('Your column')">{{ col.column }}</span>
				<span class="mr-samples" role="cell" :data-label="__('First values')">{{ col.samples.join(", ") }}</span>
				<span role="cell" :data-label="__('ERPNext field')">
					<select
						class="mr-select"
						:value="col.field || ''"
						:disabled="!review.editable || saving"
						:aria-label="__('ERPNext field for {0}', [col.column])"
						@change="change(col, $event.target.value)"
					>
						<option value="" disabled>{{ __("Choose a field") }}</option>
						<option v-for="option in review.options" :key="option.value" :value="option.value">
							{{ option.label }}{{ option.required ? " *" : "" }}
						</option>
					</select>
				</span>
				<span role="cell" :data-label="__('Status')">
					<span class="mr-status" :class="'mr-' + col.status">{{ statusLabel(col.status) }}</span>
				</span>
			</div>
		</div>
		<div class="mr-summary">{{ review.summary }}</div>
	</div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { api } from "@/api/client";
import { __ } from "@/utils/i18n";
import { logger } from "@/utils/logger";

const props = defineProps({ session: { type: String, required: true } });
const review = ref(null);
const saving = ref(false);
const error = ref("");

const LABELS = {
	mapped: () => __("Mapped"),
	not_imported: () => __("Not imported"),
	unmapped: () => __("No field"),
};
const statusLabel = (status) => (LABELS[status] || (() => status))();

async function load() {
	try {
		review.value = await api.imports.mappingReview(props.session);
	} catch (e) {
		logger.warn("mapping review:", e);
	}
}

// A changed dropdown saves at once, with no chat message, and the table shows what was saved
async function change(col, field) {
	if (!field || field === col.field) return;
	saving.value = true;
	error.value = "";
	try {
		const reply = await api.imports.setMappingColumn(props.session, col.position, field);
		if (reply?.review) review.value = reply.review;
		if (!reply?.success) {
			error.value = [reply?.error, ...(reply?.problems || [])].filter(Boolean).join(" ");
		}
	} catch (e) {
		error.value = __("The change wasn't saved.");
		logger.warn("set mapping column:", e);
		await load();
	} finally {
		saving.value = false;
	}
}

onMounted(load);
defineExpose({ load });
</script>

<style scoped>
.mapping-review {
	margin: 6px 0;
	padding: 10px 14px;
	border: 1px solid var(--ql-border);
	border-radius: 10px;
	background: var(--ql-subtle);
	color: var(--ql-text);
	font-size: 13px;
}
.mr-head { display: flex; justify-content: space-between; gap: 8px; font-weight: 600; margin-bottom: 6px; }
.mr-saving { color: var(--ql-text-muted); font-weight: 500; }
.mr-missing, .mr-locked, .mr-error {
	margin: 6px 0;
	padding: 6px 10px;
	border-radius: 8px;
	background: var(--ql-bg, #fff);
	border: 1px solid var(--ql-border);
}
.mr-missing { border-color: var(--ql-warning, #e0a43a); }
.mr-error { border-color: var(--ql-danger, #c0392b); color: var(--ql-danger, #c0392b); }
.mr-missing-field { display: inline-block; margin: 0 6px; }
.mr-hint { color: var(--ql-text-muted); margin-top: 2px; }
.mr-row {
	display: grid;
	grid-template-columns: minmax(90px, 1fr) minmax(90px, 1.2fr) minmax(140px, 1.4fr) 90px;
	gap: 8px;
	align-items: center;
	padding: 5px 0;
	border-top: 1px solid var(--ql-border);
}
.mr-header { color: var(--ql-text-muted); font-weight: 600; border-top: none; }
.mr-column { font-weight: 600; overflow-wrap: anywhere; }
.mr-samples { color: var(--ql-text-muted); overflow-wrap: anywhere; }
.mr-select { width: 100%; max-width: 100%; padding: 4px 6px; border-radius: 6px; border: 1px solid var(--ql-border); background: var(--ql-bg, #fff); color: var(--ql-text); }
.mr-status { padding: 1px 8px; border-radius: 999px; border: 1px solid var(--ql-border); white-space: nowrap; }
.mr-mapped { border-color: var(--ql-accent); color: var(--ql-accent); }
.mr-unmapped { border-color: var(--ql-warning, #e0a43a); }
.mr-summary { margin-top: 6px; color: var(--ql-text-muted); }

/* A phone (375px): each column is a small block of its own, labels in front */
@media (max-width: 480px) {
	.mr-header { display: none; }
	.mr-row { grid-template-columns: 1fr; gap: 2px; padding: 8px 0; }
	.mr-row [role="cell"]::before {
		content: attr(data-label) ": ";
		color: var(--ql-text-muted);
		font-weight: 500;
	}
}
</style>
