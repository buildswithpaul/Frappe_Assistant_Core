<template>
	<div class="config-section">
		<div class="prompt-header">
			<label class="config-label" :for="fieldId">System Prompt</label>
			<VariableInserter
				v-if="!readonly"
				:global-variables="variables"
				@insert="insertVariable"
			/>
		</div>

		<textarea
			:id="fieldId"
			ref="textareaRef"
			:value="modelValue"
			class="config-input config-textarea"
			placeholder="You are a helpful assistant that..."
			rows="6"
			:readonly="readonly"
			@input="$emit('update:modelValue', $event.target.value)"
		></textarea>

		<div class="prompt-meta">
			<button class="disclosure" @click="showPreview = !showPreview">
				<span class="disclosure-caret" :class="{ open: showPreview }">›</span>
				{{ showPreview ? "Hide" : "Preview" }} resolved prompt
			</button>
			<span class="length-estimate" title="Length of the resolved prompt"
				>{{ preview.text.length.toLocaleString("en-US") }} characters</span
			>
		</div>

		<div v-if="showPreview" class="prompt-preview">
			<p class="preview-caption">
				What the model receives: your prompt with variables substituted, plus the tool block
				the engine appends.
			</p>
			<pre class="preview-body">{{ preview.text || "(empty prompt)" }}</pre>
			<p v-if="preview.unresolvedVariables.length" class="preview-warn">
				Undefined variables — these render empty at run time:
				{{ preview.unresolvedVariables.join(", ") }}
			</p>
			<p v-if="preview.missingTools.length" class="preview-warn">
				Unavailable tools: {{ preview.missingTools.join(", ") }}
			</p>
		</div>
	</div>
</template>

<script setup>
import { ref, computed } from "vue";
import VariableInserter from "./VariableInserter.vue";
import { buildResolvedPrompt } from "./promptPreview";

const props = defineProps({
	modelValue: { type: String, default: "" },
	/** Workflow-level global_settings.variables. */
	variables: { type: Object, default: () => ({}) },
	directives: { type: Array, default: () => [] },
	/** Map of directive tool_name -> resolve_workflow_tools entry. */
	resolution: { type: Map, default: () => new Map() },
	readonly: { type: Boolean, default: false },
});

const emit = defineEmits(["update:modelValue"]);

const fieldId = `system-prompt-${Math.random().toString(36).slice(2, 8)}`;
const textareaRef = ref(null);
const showPreview = ref(false);

const preview = computed(() =>
	buildResolvedPrompt({
		systemPrompt: props.modelValue,
		variables: props.variables,
		directives: props.directives,
		resolution: props.resolution,
	})
);

function insertVariable(placeholder) {
	const el = textareaRef.value;
	const current = props.modelValue || "";
	if (!el) {
		emit("update:modelValue", current + placeholder);
		return;
	}
	const start = el.selectionStart ?? current.length;
	const end = el.selectionEnd ?? current.length;
	emit("update:modelValue", current.slice(0, start) + placeholder + current.slice(end));
}
</script>

<style scoped>
.config-section {
	margin-bottom: 1rem;
}

.prompt-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 0.5rem;
	margin-bottom: 0.375rem;
}

.config-label {
	display: block;
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.025em;
	margin-bottom: 0;
}

.config-input {
	width: 100%;
	padding: 0.5rem 0.625rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	outline: none;
	box-sizing: border-box;
	transition: border-color 0.15s ease;
}

.config-input:focus {
	border-color: var(--ql-accent);
}

.config-textarea {
	resize: vertical;
	min-height: 3rem;
	font-family: inherit;
	line-height: 1.5;
}

.prompt-meta {
	display: flex;
	align-items: center;
	justify-content: space-between;
	margin-top: 0.25rem;
}

.disclosure {
	display: inline-flex;
	align-items: center;
	gap: 0.25rem;
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	background: transparent;
	border: none;
	padding: 0;
	cursor: pointer;
}

.disclosure:hover {
	color: var(--ql-accent);
}

.disclosure-caret {
	display: inline-block;
	transition: transform 0.15s ease;
}

.disclosure-caret.open {
	transform: rotate(90deg);
}

.length-estimate {
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
}

.prompt-preview {
	margin-top: 0.5rem;
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	background: var(--ql-subtle);
	padding: 0.5rem;
}

.preview-caption {
	margin: 0 0 0.375rem;
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	line-height: 1.4;
}

.preview-body {
	margin: 0;
	max-height: 16rem;
	overflow: auto;
	font-family: "SF Mono", Monaco, "Cascadia Code", monospace;
	font-size: 0.6875rem;
	line-height: 1.5;
	color: var(--ql-text);
	white-space: pre-wrap;
	word-break: break-word;
}

.preview-warn {
	margin: 0.375rem 0 0;
	font-size: 0.6875rem;
	color: var(--ql-danger);
	line-height: 1.4;
}
</style>
