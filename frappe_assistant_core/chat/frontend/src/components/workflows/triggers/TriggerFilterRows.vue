<template>
	<div class="filter-rows">
		<div v-for="(row, idx) in rows" :key="idx" class="filter-row">
			<div class="filter-row-picker">
				<LinkPicker
					v-model="row.fieldname"
					:options="fieldOptions"
					:placeholder="__('fieldname')"
					:empty-text="__('No matching field')"
				/>
			</div>
			<select v-model="row.operator" class="field-input narrow">
				<option v-for="op in OPERATORS" :key="op" :value="op">{{ op }}</option>
			</select>
			<input
				v-model="row.value"
				class="field-input"
				:placeholder="__('value')"
				:disabled="['is set', 'is not set'].includes(row.operator)"
			/>
			<button
				type="button"
				class="icon-btn danger"
				:aria-label="__('Remove filter')"
				@click="rows.splice(idx, 1)"
			>
				×
			</button>
		</div>
		<button
			type="button"
			class="action-btn small"
			@click="rows.push({ fieldname: '', operator: '=', value: '' })"
		>
			{{ __("+ Add filter") }}
		</button>
	</div>
</template>

<script setup>
import { __ } from "@/utils/i18n";
import LinkPicker from "./LinkPicker.vue";

// `rows` is the editor's reactive form.filters array, edited in place.
defineProps({
	rows: { type: Array, required: true },
	fieldOptions: { type: Array, default: () => [] },
});

const OPERATORS = ["=", "!=", ">", "<", ">=", "<=", "in", "not in", "is set", "is not set"];
</script>

<style scoped>
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
	padding: 0.25rem 0.625rem;
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-text);
	background: var(--ql-subtle);
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	align-self: flex-start;
	transition: all 0.15s ease;
}
.action-btn:hover {
	background-color: var(--ql-border);
}
</style>
