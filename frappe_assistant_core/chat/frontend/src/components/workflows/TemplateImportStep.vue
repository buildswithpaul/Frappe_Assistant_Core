<template>
	<div class="import-step">
		<div class="modal-header">
			<button @click="$emit('back')" class="back-btn">
				<svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M15 19l-7-7 7-7"
					/>
				</svg>
				{{ __("Back to details") }}
			</button>
			<button @click="$emit('close')" class="close-btn" :title="__('Close')" :aria-label="__('Close')">
				<svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M6 18L18 6M6 6l12 12"
					/>
				</svg>
			</button>
		</div>

		<div class="import-content">
			<!-- Template info -->
			<div class="tpl-info">
				<h3 class="tpl-info-name">
					<svg
						v-if="template.is_official"
						class="verified-icon"
						width="16"
						height="16"
						viewBox="0 0 24 24"
						fill="currentColor"
					>
						<path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
					</svg>
					{{ template.template_name }}
				</h3>
				<span class="tpl-info-category">{{ template.category || __("General") }}</span>
				<p v-if="template.description" class="tpl-info-desc">{{ template.description }}</p>
				<div v-if="template.agent_count" class="tpl-info-stats">
					{{ __("{0} task(s)", [template.agent_count]) }}
				</div>
			</div>

			<!-- Workflow name -->
			<div class="form-field">
				<label class="field-label">{{ __("Agent Name") }}</label>
				<input
					v-model="importName"
					class="field-input"
					:placeholder="__('Name for the new agent')"
					ref="importNameRef"
				/>
			</div>

			<template v-if="fields.length > 0">
				<div class="variables-section">
					<h4 class="variables-title">{{ __("Template Variables") }}</h4>
					<TemplateVariableField
						v-for="field in fields"
						:key="field.key"
						:field="field"
						:model-value="values[field.key]"
						:error="errors[field.key] || ''"
						@update:model-value="values[field.key] = $event"
					/>
				</div>
			</template>

			<!-- Warnings -->
			<div v-if="requiredTools.length > 0" class="warnings-box">
				<p class="warning-item">
					{{
						__("This template uses {0} tool(s): {1}", [
							requiredTools.length,
							requiredTools.join(", "),
						])
					}}
				</p>
			</div>

			<div class="form-actions">
				<button @click="$emit('back')" class="action-btn">{{ __("Cancel") }}</button>
				<button
					@click="handleImport"
					class="action-btn primary"
					:disabled="!importName.trim() || isBusy"
					data-test="import-submit"
				>
					{{ isBusy ? __("Creating...") : __("Create from Template") }}
				</button>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, nextTick, reactive, ref, watch } from "vue";
import { __ } from "@/utils/i18n";
import TemplateVariableField from "./marketplace/TemplateVariableField.vue";
import {
	coerceVariables,
	initialValues,
	legacyRequiredTools,
	normalizeVariableSchema,
	validateVariables,
} from "./marketplace/templateSchema";

const props = defineProps({
	template: { type: Object, required: true },
	isBusy: { type: Boolean, default: false },
});

const emit = defineEmits(["back", "close", "import"]);

const importName = ref("");
const values = reactive({});
const attempted = ref(false);
const importNameRef = ref(null);

const fields = computed(() =>
	normalizeVariableSchema(props.template?.variables_schema, props.template?.default_variables)
);
const errors = computed(() => (attempted.value ? validateVariables(fields.value, values) : {}));
const requiredTools = computed(() => legacyRequiredTools(props.template));

watch(
	() => props.template,
	async (tpl) => {
		if (!tpl) return;
		importName.value = tpl.template_name || "";
		attempted.value = false;
		for (const k of Object.keys(values)) delete values[k];
		Object.assign(values, initialValues(fields.value));
		await nextTick();
		importNameRef.value?.focus();
	},
	{ immediate: true }
);

function handleImport() {
	if (!importName.value.trim() || props.isBusy) return;
	attempted.value = true;
	if (Object.keys(validateVariables(fields.value, values)).length) return;
	emit("import", { name: importName.value.trim(), variables: coerceVariables(fields.value, values) });
}
</script>

<style scoped>
.import-step {
	display: flex;
	flex-direction: column;
	height: 100%;
	min-height: 0;
}

.modal-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 1rem 1.25rem;
	border-bottom: 1px solid var(--ql-border);
	flex-shrink: 0;
}

.close-btn {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 28px;
	height: 28px;
	background: transparent;
	border: none;
	color: var(--ql-text-muted);
	border-radius: 0.25rem;
	cursor: pointer;
	transition: all 0.15s ease;
	flex-shrink: 0;
}

.close-btn:hover {
	background: var(--ql-subtle);
	color: var(--ql-text);
}

.back-btn {
	display: flex;
	align-items: center;
	gap: 0.375rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text-muted);
	background: transparent;
	border: none;
	cursor: pointer;
	padding: 0.25rem 0;
	transition: color 0.15s ease;
}

.back-btn:hover {
	color: var(--ql-text);
}

.import-content {
	padding: 1.25rem;
	overflow-y: auto;
	flex: 1;
	min-height: 0;
	display: flex;
	flex-direction: column;
}

.tpl-info {
	background: var(--ql-subtle);
	border-radius: 0.5rem;
	padding: 0.875rem 1rem;
	margin-bottom: 1.25rem;
}

.tpl-info-name {
	font-size: 1rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0 0 0.25rem;
	display: flex;
	align-items: center;
	gap: 0.375rem;
}

.verified-icon {
	color: var(--ql-accent);
	flex-shrink: 0;
}

.tpl-info-category {
	font-size: 0.625rem;
	font-weight: 600;
	padding: 0.125rem 0.375rem;
	border-radius: 9999px;
	text-transform: uppercase;
	letter-spacing: 0.03em;
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
}

.tpl-info-desc {
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
	margin: 0.5rem 0 0;
	line-height: 1.4;
}

.tpl-info-stats {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	margin-top: 0.375rem;
}

.variables-section {
	margin-top: 1rem;
}

.variables-title {
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.025em;
	margin: 0 0 0.75rem;
}

.form-field {
	margin-bottom: 1rem;
}

.field-label {
	display: block;
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text);
	margin-bottom: 0.375rem;
}


.field-input {
	width: 100%;
	padding: 0.5rem 0.75rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	outline: none;
	transition: border-color 0.15s ease;
	box-sizing: border-box;
}

.field-input:focus {
	border-color: var(--ql-accent);
}




.warnings-box {
	background: rgba(245, 158, 11, 0.08);
	border: 1px solid rgba(245, 158, 11, 0.25);
	border-radius: 0.5rem;
	padding: 0.625rem 0.75rem;
	margin-top: 0.75rem;
}

.warning-item {
	font-size: 0.75rem;
	color: var(--ql-warning);
	margin: 0;
	line-height: 1.4;
}

.warning-item + .warning-item {
	margin-top: 0.25rem;
}

.form-actions {
	display: flex;
	justify-content: flex-end;
	gap: 0.5rem;
	margin-top: auto;
	padding-top: 1.25rem;
	position: sticky;
	bottom: 0;
	background: var(--ql-surface);
	padding-bottom: 0.25rem;
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

.action-btn.primary {
	color: white;
	background-color: var(--ql-accent);
}

.action-btn.primary:hover {
	background-color: var(--ql-accent-hover);
}

.action-btn.primary:disabled {
	opacity: 0.6;
	cursor: not-allowed;
}
</style>
