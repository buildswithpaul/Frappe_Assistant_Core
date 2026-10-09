<template>
	<div class="var-field">
		<label class="var-label" :for="inputId">
			{{ field.label }}
			<span v-if="!field.required" class="var-optional">{{ __("(optional)") }}</span>
		</label>

		<LinkPicker
			v-if="field.type === 'link'"
			:model-value="modelValue || ''"
			:fetcher="searchDocs"
			:placeholder="__('Search {0}…', [field.options])"
			:empty-text="__('No {0} matches', [field.options])"
			@update:model-value="$emit('update:modelValue', $event)"
		/>
		<label v-else-if="field.type === 'check'" class="var-check">
			<input :id="inputId" type="checkbox" :checked="!!modelValue" @change="$emit('update:modelValue', $event.target.checked)" />
			<span>{{ field.description || field.label }}</span>
		</label>
		<select
			v-else-if="field.type === 'select'"
			:id="inputId"
			class="var-input"
			:class="{ invalid: error }"
			:value="modelValue"
			@change="$emit('update:modelValue', $event.target.value)"
		>
			<option value="">{{ __("Choose…") }}</option>
			<option v-for="opt in field.options" :key="opt" :value="opt">{{ opt }}</option>
		</select>
		<textarea
			v-else-if="field.type === 'text' && field.description.length > 80"
			:id="inputId"
			class="var-input var-textarea"
			:class="{ invalid: error }"
			rows="3"
			:value="modelValue"
			@input="$emit('update:modelValue', $event.target.value)"
		></textarea>
		<input
			v-else
			:id="inputId"
			class="var-input"
			:class="{ invalid: error }"
			:type="field.type === 'email' ? 'email' : field.type === 'int' || field.type === 'float' ? 'number' : 'text'"
			:step="field.type === 'int' ? '1' : field.type === 'float' ? 'any' : undefined"
			:aria-invalid="!!error"
			:value="modelValue"
			@input="$emit('update:modelValue', $event.target.value)"
		/>

		<p v-if="error" class="var-error" role="alert">{{ error }}</p>
		<p v-else-if="field.description && field.type !== 'check'" class="var-hint">{{ field.description }}</p>
	</div>
</template>

<script setup>
import { __ } from "@/utils/i18n";
import { api } from "@/api/client";
import LinkPicker from "../triggers/LinkPicker.vue";

const props = defineProps({
	field: { type: Object, required: true },
	modelValue: { type: [String, Number, Boolean], default: "" },
	error: { type: String, default: "" },
});
defineEmits(["update:modelValue"]);

const inputId = `var-${props.field.key}-${Math.random().toString(36).slice(2, 6)}`;

async function searchDocs(query) {
	const res = await api.workflows.searchLink(props.field.options, query);
	const rows = Array.isArray(res) ? res : res?.results || [];
	return {
		options: rows.map((r) => ({ value: r.value, label: r.label || r.value, description: r.description || "" })),
		total: rows.length,
	};
}
</script>

<style scoped>
.var-field {
	margin-bottom: 0.875rem;
}
.var-label {
	display: block;
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text);
	margin-bottom: 0.25rem;
}
.var-optional {
	font-weight: 400;
	color: var(--ql-text-muted);
}
.var-input {
	width: 100%;
	padding: 0.5rem 0.625rem;
	font-size: 0.875rem;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-sm);
}
.var-input:focus {
	outline: none;
	border-color: var(--ql-accent);
}
.var-input.invalid,
.var-input.invalid:focus {
	border-color: var(--ql-danger);
}
.var-textarea {
	resize: vertical;
}
.var-check {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
}
.var-error {
	margin-top: 0.25rem;
	font-size: 0.75rem;
	color: var(--ql-danger);
}
.var-hint {
	margin-top: 0.25rem;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}
</style>
