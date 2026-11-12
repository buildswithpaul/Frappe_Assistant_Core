<template>
	<dl v-if="card" class="import-approval">
		<div>
			<dt>{{ __("File") }}</dt>
			<dd>{{ card.file_name }}</dd>
		</div>
		<div>
			<dt>{{ __("Into") }}</dt>
			<dd>{{ card.update ? __("Updates to {0} records", [card.doctype]) : __("New {0} records", [card.doctype]) }}</dd>
		</div>
		<div v-if="rows !== null">
			<dt>{{ card.update ? __("Updated") : __("Created") }}</dt>
			<dd>{{ __("{0} rows", [rows]) }}</dd>
		</div>
		<div v-if="card.left_out">
			<dt>{{ __("Left out") }}</dt>
			<dd>{{ __("{0} rows", [card.left_out]) }}</dd>
		</div>
		<div v-if="card.submit">
			<dt>{{ __("Then") }}</dt>
			<dd class="ia-submit">{{ __("Will be submitted") }}</dd>
		</div>
		<div v-if="card.mapping" class="ia-mapping">
			<dt>{{ __("Columns") }}</dt>
			<dd>{{ card.mapping }}</dd>
		</div>
		<div v-if="card.changes" class="ia-changes">
			<dt>{{ __("Changes") }}</dt>
			<dd>
				<div>{{ __("{0} changes in {1} records", [card.changes.fields, card.changes.records]) }}</div>
				<ul class="ia-samples">
					<li v-for="sample in card.changes.samples" :key="sample.record">
						<span class="ia-record">{{ sample.record }}</span>
						<span v-for="change in sample.changes" :key="change.label" class="ia-change">
							{{ change.label }}: {{ change.old || __("(empty)") }} → {{ change.new || __("(empty)") }}
						</span>
					</li>
				</ul>
				<div v-if="card.changes.records > card.changes.samples.length" class="ia-more">
					{{ __("and {0} more records", [card.changes.records - card.changes.samples.length]) }}
				</div>
			</dd>
		</div>
	</dl>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { api } from "@/api/client";
import { __ } from "@/utils/i18n";
import { logger } from "@/utils/logger";

// The approval card of start_import (#34415): the tool's figures are the input; the file, the rows
// left out and the mapping are the session's. An update shows what changes, old and new values from
// its last check (PR #392, F6). No <p>: a turn's paragraph rule restyles it (cf8e5fa8).
const props = defineProps({ input: { type: Object, required: true } });
const card = ref(null);
const rows = computed(() => (Number.isFinite(Number(props.input.rows)) ? Number(props.input.rows) : card.value?.rows ?? null));

onMounted(async () => {
	if (!props.input.session) return;
	try {
		card.value = await api.imports.importCard(props.input.session);
	} catch (e) {
		logger.warn("import card:", e);
	}
});
</script>

<style scoped>
.import-approval {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
	gap: 6px 14px;
	margin: 6px 0 4px;
	font-size: 13px;
}
.import-approval dt { color: var(--ql-text-muted); font-weight: 500; }
.import-approval dd { margin: 0; overflow-wrap: anywhere; color: var(--ql-text); }
.ia-mapping { grid-column: 1 / -1; }
.ia-submit { color: var(--ql-warning, #b36b00); font-weight: 600; }
.ia-changes { grid-column: 1 / -1; }
.ia-samples { margin: 4px 0 0; padding-left: 16px; }
.ia-samples li { margin: 2px 0; }
.ia-record { font-weight: 600; margin-right: 6px; }
.ia-change { display: inline-block; margin-right: 10px; color: var(--ql-text-muted); }
.ia-more { color: var(--ql-text-muted); }
</style>
