<template>
	<li class="tool-permission-row" data-test="tool-row">
		<div class="tool-permission-row__identity">
			<span class="tool-permission-row__name">{{ tool.name }}</span>
			<span v-if="tool.description" class="tool-permission-row__description">
				{{ tool.description }}
			</span>
		</div>

		<div
			class="tool-permission-row__choices"
			role="radiogroup"
			:aria-label="`Permission for ${tool.name}`"
		>
			<button
				v-for="choice in CHOICES"
				:key="choice.value"
				type="button"
				role="radio"
				:aria-checked="modelValue === choice.value"
				:class="[
					'tool-permission-row__choice',
					`tool-permission-row__choice--${choice.value}`,
					{ 'is-selected': modelValue === choice.value },
				]"
				:title="choice.hint"
				:data-test="`choice-${choice.value}`"
				@click="$emit('update:modelValue', choice.value)"
			>
				{{ choice.label }}
			</button>
		</div>
	</li>
</template>

<script setup>
// Mirrors AR's three approval outcomes. "blocked" is the only one that also
// removes the tool from what the model is shown at all — the other two decide
// what happens when it is called.
const CHOICES = [
	{ value: "always", label: "Always allow", hint: "Runs without asking you." },
	{ value: "ask", label: "Ask", hint: "Pauses for your approval every time." },
	{ value: "blocked", label: "Blocked", hint: "Hidden from the assistant entirely." },
];

defineProps({
	tool: { type: Object, required: true },
	modelValue: { type: String, required: true },
});

defineEmits(["update:modelValue"]);
</script>

<style scoped>
.tool-permission-row {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: var(--ql-space-4);
	padding: var(--ql-space-3) var(--ql-space-4);
	border-bottom: 1px solid var(--ql-border);
}

.tool-permission-row:last-child {
	border-bottom: none;
}

.tool-permission-row__identity {
	display: flex;
	flex-direction: column;
	gap: 2px;
	min-width: 0;
}

.tool-permission-row__name {
	font-family: var(--ql-font-mono);
	font-size: 0.8125rem;
	color: var(--ql-text);
}

.tool-permission-row__description {
	overflow: hidden;
	font-size: 0.75rem;
	line-height: 1.4;
	color: var(--ql-text-muted);
	text-overflow: ellipsis;
	display: -webkit-box;
	-webkit-line-clamp: 2;
	-webkit-box-orient: vertical;
}

.tool-permission-row__choices {
	display: inline-flex;
	flex-shrink: 0;
	padding: 2px;
	background: var(--ql-subtle);
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-sm);
}

.tool-permission-row__choice {
	padding: 4px 10px;
	border: none;
	border-radius: 4px;
	background: none;
	font: inherit;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	white-space: nowrap;
	cursor: pointer;
}

.tool-permission-row__choice:hover {
	color: var(--ql-text);
}

.tool-permission-row__choice.is-selected {
	background: var(--ql-surface);
	box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
}

.tool-permission-row__choice--always.is-selected {
	color: var(--ql-success);
}

.tool-permission-row__choice--ask.is-selected {
	color: var(--ql-text);
}

.tool-permission-row__choice--blocked.is-selected {
	color: var(--ql-danger);
}

@media (max-width: 34rem) {
	.tool-permission-row {
		flex-direction: column;
		align-items: stretch;
		gap: var(--ql-space-2);
	}

	.tool-permission-row__choices {
		align-self: flex-start;
	}
}
</style>
