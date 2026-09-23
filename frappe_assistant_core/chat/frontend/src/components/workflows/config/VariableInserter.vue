<template>
	<div class="variable-inserter" v-if="variables.length > 0">
		<div class="inserter-trigger">
			<button
				type="button"
				class="insert-btn"
				@click="open = !open"
				:title="open ? 'Close variable picker' : 'Insert variable placeholder'"
				aria-label="Insert variable placeholder"
			>
				<svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z"
					/>
				</svg>
				<span v-pre>{{ ... }}</span>
			</button>
		</div>

		<div v-if="open" class="inserter-dropdown">
			<div v-for="v in variables" :key="v" class="inserter-item" @click="insert(v)">
				<code>{{ placeholder(v) }}</code>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref, computed } from "vue";

const props = defineProps({
	/** Object of { variable_name: value } from globalSettings.variables */
	globalVariables: { type: Object, default: () => ({}) },
});

const emit = defineEmits(["insert"]);

const open = ref(false);

const variables = computed(() => Object.keys(props.globalVariables || {}));

// The literal cannot live in the template: Vue ends an interpolation at the
// first "}}", so an inline `{{ '{{' + v + '}}' }}` fails to compile at all.
function placeholder(varName) {
	return `{{${varName}}}`;
}

function insert(varName) {
	emit("insert", placeholder(varName));
	open.value = false;
}
</script>

<style scoped>
.variable-inserter {
	position: relative;
	display: inline-block;
}

.insert-btn {
	display: inline-flex;
	align-items: center;
	gap: 0.25rem;
	padding: 0.25rem 0.5rem;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	background: transparent;
	border: 1px solid var(--ql-border);
	border-radius: 4px;
	cursor: pointer;
	transition: all 0.15s;
}

.insert-btn:hover {
	color: var(--ql-accent);
	border-color: var(--ql-accent);
}

.inserter-dropdown {
	position: absolute;
	top: 100%;
	left: 0;
	margin-top: 4px;
	min-width: 160px;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 6px;
	box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
	z-index: 20;
	max-height: 200px;
	overflow-y: auto;
}

.inserter-item {
	padding: 0.5rem 0.75rem;
	cursor: pointer;
	font-size: 0.8125rem;
	transition: background 0.1s;
}

.inserter-item:hover {
	background: var(--ql-subtle);
}

.inserter-item code {
	font-family: monospace;
	font-size: 0.8125rem;
	color: var(--ql-accent);
}
</style>
