<template>
	<!-- Condition -->
	<template v-if="nodeType === 'condition'">
		<div class="config-section">
			<label class="config-label">Field Name</label>
			<input
				v-model="config.condition_field"
				class="config-input"
				placeholder="e.g., status, category, score"
				:readonly="readonly"
				@input="$emit('update')"
			/>
			<p class="config-hint">The field in the input data to evaluate.</p>
		</div>

		<div class="config-section">
			<label class="config-label">Operator</label>
			<select
				v-model="config.condition_operator"
				class="config-input config-select"
				:disabled="readonly"
				@change="$emit('update')"
			>
				<option v-for="op in CONDITION_OPERATORS" :key="op.value" :value="op.value">
					{{ op.label }}
				</option>
			</select>
		</div>

		<div v-if="config.condition_operator !== 'is_truthy'" class="config-section">
			<label class="config-label">Value</label>
			<input
				v-model="config.condition_value"
				class="config-input"
				placeholder="Value to compare against"
				:readonly="readonly"
				@input="$emit('update')"
			/>
		</div>

		<div class="config-info">
			<p><strong>Pass (top)</strong> → when condition is true</p>
			<p><strong>Fail (bottom)</strong> → when condition is false</p>
		</div>
	</template>

	<!-- Transform -->
	<template v-else-if="nodeType === 'transform'">
		<div class="config-section">
			<label class="config-label">Jinja2 Template</label>
			<textarea
				v-model="config.transform_template"
				class="config-input config-textarea mono"
				placeholder="{{ input | upper }}"
				rows="8"
				:readonly="readonly"
				@input="$emit('update')"
			></textarea>
			<p class="config-hint">
				Use Jinja2 syntax. Available variables: <code>input</code>,
				<code>variables</code>.
			</p>
		</div>
	</template>

	<!-- Input -->
	<template v-else-if="nodeType === 'workflow-input'">
		<div class="config-section">
			<label class="config-label"
				>Description <span class="optional">(optional)</span></label
			>
			<textarea
				v-model="config.description"
				class="config-input config-textarea"
				placeholder="Describe the expected input format..."
				rows="3"
				:readonly="readonly"
				@input="$emit('update')"
			></textarea>
		</div>
		<div class="config-info">
			<p>
				The input node is the entry point of your workflow. When triggered, the input data
				will be passed to connected nodes.
			</p>
		</div>
	</template>

	<!-- Output -->
	<template v-else-if="nodeType === 'workflow-output'">
		<div class="config-section">
			<label class="config-label"
				>Output Template <span class="optional">(optional)</span></label
			>
			<textarea
				v-model="config.output_template"
				class="config-input config-textarea mono"
				placeholder="{{ input }}"
				rows="5"
				:readonly="readonly"
				@input="$emit('update')"
			></textarea>
			<p class="config-hint">
				Jinja2 template to format the final output. Leave blank to pass through.
			</p>
		</div>
	</template>
</template>

<script setup>
import { CONDITION_OPERATORS } from "../graphUtils";

defineProps({
	nodeType: { type: String, required: true },
	config: { type: Object, required: true },
	readonly: { type: Boolean, default: false },
});

defineEmits(["update"]);
</script>

<style scoped>
.config-section {
	margin-bottom: 1rem;
}

.config-label {
	display: block;
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.025em;
	margin-bottom: 0.375rem;
}

.config-label .optional {
	font-weight: 400;
	text-transform: none;
	letter-spacing: 0;
	opacity: 0.7;
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

.config-textarea.mono {
	font-family: "SF Mono", Monaco, "Cascadia Code", monospace;
	font-size: 0.75rem;
	line-height: 1.6;
}

.config-select {
	cursor: pointer;
	appearance: none;
	background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e");
	background-position: right 0.5rem center;
	background-repeat: no-repeat;
	background-size: 1em;
	padding-right: 2rem;
}

.config-hint {
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	margin: 0.25rem 0 0;
	line-height: 1.4;
}

.config-hint code {
	background: var(--ql-subtle);
	padding: 0.0625rem 0.25rem;
	border-radius: 0.1875rem;
	font-size: 0.6875rem;
}

.config-info {
	background: var(--ql-subtle);
	border-radius: 0.375rem;
	padding: 0.625rem 0.75rem;
	margin-top: 0.75rem;
}

.config-info p {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	margin: 0;
	line-height: 1.5;
}

.config-info p + p {
	margin-top: 0.25rem;
}

.config-info strong {
	color: var(--ql-text);
	font-weight: 600;
}
</style>
