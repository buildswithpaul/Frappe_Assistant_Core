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
				Back to details
			</button>
			<button @click="$emit('close')" class="close-btn" title="Close" aria-label="Close">
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
				<span class="tpl-info-category">{{ template.category || "General" }}</span>
				<p v-if="template.description" class="tpl-info-desc">{{ template.description }}</p>
				<div v-if="template.agent_count" class="tpl-info-stats">
					{{ template.agent_count }} task{{ template.agent_count !== 1 ? "s" : "" }}
				</div>
			</div>

			<!-- Workflow name -->
			<div class="form-field">
				<label class="field-label">Agent Name</label>
				<input
					v-model="importName"
					class="field-input"
					placeholder="Name for the new agent"
					ref="importNameRef"
				/>
			</div>

			<!-- Variable form (dynamic from variables_schema) -->
			<template v-if="variableFields.length > 0">
				<div class="variables-section">
					<h4 class="variables-title">Template Variables</h4>
					<div v-for="field in variableFields" :key="field.key" class="form-field">
						<label class="field-label">
							{{ field.label }}
							<span v-if="!field.required" class="optional">(optional)</span>
						</label>
						<select
							v-if="field.options"
							v-model="importVariables[field.key]"
							class="field-input field-select"
						>
							<option v-for="opt in field.options" :key="opt" :value="opt">
								{{ opt }}
							</option>
						</select>
						<textarea
							v-else-if="field.long"
							v-model="importVariables[field.key]"
							class="field-input field-textarea"
							:placeholder="field.description || ''"
							rows="3"
						></textarea>
						<input
							v-else
							v-model="importVariables[field.key]"
							class="field-input"
							:placeholder="field.description || ''"
						/>
						<p v-if="field.description" class="field-hint">{{ field.description }}</p>
					</div>
				</div>
			</template>

			<!-- Warnings -->
			<div v-if="warnings.length > 0" class="warnings-box">
				<p v-for="(w, i) in warnings" :key="i" class="warning-item">{{ w }}</p>
			</div>

			<div class="form-actions">
				<button @click="$emit('back')" class="action-btn">Cancel</button>
				<button
					@click="handleImport"
					class="action-btn primary"
					:disabled="!importName.trim() || isBusy"
				>
					{{ isBusy ? "Creating..." : "Create from Template" }}
				</button>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick } from "vue";

const props = defineProps({
	template: { type: Object, required: true },
	isBusy: { type: Boolean, default: false },
});

const emit = defineEmits(["back", "close", "import"]);

const importName = ref("");
const importVariables = reactive({});
const warnings = ref([]);
const importNameRef = ref(null);

const variableFields = computed(() => {
	const tpl = props.template;
	if (!tpl?.variables_schema) return [];

	const schema =
		typeof tpl.variables_schema === "string"
			? JSON.parse(tpl.variables_schema)
			: tpl.variables_schema;

	return Object.entries(schema).map(([key, def]) => ({
		key,
		label: key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
		description: def.description || "",
		required: !!def.required,
		options: def.enum || null,
		long: def.type === "text" || (def.description && def.description.length > 80),
	}));
});

// Initialize when template changes
watch(
	() => props.template,
	async (tpl) => {
		if (!tpl) return;

		importName.value = tpl.template_name || "";

		// Reset and pre-fill variables from defaults
		Object.keys(importVariables).forEach((k) => delete importVariables[k]);
		const defaults = tpl.default_variables
			? typeof tpl.default_variables === "string"
				? JSON.parse(tpl.default_variables)
				: tpl.default_variables
			: {};
		Object.assign(importVariables, defaults);

		// Check tool compatibility warnings.
		// `required_tools` may arrive as an array (already parsed) or as a JSON
		// string from a Long Text / JSON DocType field — normalize both.
		const requiredTools = (() => {
			const raw = tpl.required_tools;
			if (!raw) return [];
			if (Array.isArray(raw)) return raw;
			if (typeof raw === "string") {
				const trimmed = raw.trim();
				if (!trimmed) return [];
				try {
					const parsed = JSON.parse(trimmed);
					return Array.isArray(parsed) ? parsed : [];
				} catch {
					return trimmed
						.split(/[,\n]/)
						.map((t) => t.trim())
						.filter(Boolean);
				}
			}
			return [];
		})();

		if (requiredTools.length) {
			warnings.value = [
				`This template requires ${requiredTools.length} tool(s): ${requiredTools.join(
					", "
				)}`,
			];
		} else {
			warnings.value = [];
		}

		await nextTick();
		importNameRef.value?.focus();
	},
	{ immediate: true }
);

function handleImport() {
	if (!importName.value.trim() || props.isBusy) return;
	const vars = Object.keys(importVariables).length > 0 ? { ...importVariables } : null;
	emit("import", { name: importName.value.trim(), variables: vars });
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

.field-label .optional {
	font-weight: 400;
	color: var(--ql-text-muted);
	font-size: 0.75rem;
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

.field-textarea {
	resize: vertical;
	min-height: 3.5rem;
	font-family: inherit;
	line-height: 1.5;
}

.field-select {
	cursor: pointer;
	appearance: none;
	background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e");
	background-position: right 0.5rem center;
	background-repeat: no-repeat;
	background-size: 1em;
	padding-right: 2rem;
}

.field-hint {
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	margin: 0.25rem 0 0;
	line-height: 1.4;
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
