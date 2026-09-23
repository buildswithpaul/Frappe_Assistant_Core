<template>
	<div v-if="endpointUrl" class="external-clients-panel" data-test="external-clients-panel">
		<div class="external-clients-panel__text">
			<h3 class="external-clients-panel__heading">Point other apps at this ERP</h3>
			<p class="external-clients-panel__body">
				Claude Desktop, Cursor and other MCP clients can reach it at this address.
			</p>
		</div>
		<div class="external-clients-panel__url-row">
			<code class="external-clients-panel__url">{{ endpointUrl }}</code>
			<button
				type="button"
				class="external-clients-panel__copy"
				data-test="copy"
				@click="copyUrl"
			>
				{{ copied ? "Copied" : "Copy" }}
			</button>
		</div>
	</div>
</template>

<script setup>
import { ref } from "vue";

const props = defineProps({
	endpointUrl: { type: String, default: "" },
});

const copied = ref(false);

async function copyUrl() {
	try {
		await navigator.clipboard.writeText(props.endpointUrl);
		copied.value = true;
		setTimeout(() => (copied.value = false), 1500);
	} catch {
		copied.value = false;
	}
}
</script>

<style scoped>
/* The other direction: everything above is what this assistant reaches out to,
   this is how something else reaches in. Seated rather than raised, so it reads
   as a footnote to the ledger instead of another entry in it. */
.external-clients-panel {
	display: flex;
	flex-direction: column;
	gap: var(--ql-space-3);
	padding: var(--ql-space-4) var(--ql-space-6);
	border-radius: var(--ql-radius-lg);
	background: var(--ql-subtle);
}

.external-clients-panel__heading {
	margin: 0;
	font-size: 0.8125rem;
	font-weight: 600;
	color: var(--ql-text-secondary);
}

.external-clients-panel__body {
	margin: 2px 0 0;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.external-clients-panel__url-row {
	display: flex;
	align-items: center;
	gap: var(--ql-space-2);
	flex-wrap: wrap;
}

.external-clients-panel__url {
	flex: 1;
	min-width: 0;
	padding: 7px 10px;
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-sm);
	background: var(--ql-surface);
	color: var(--ql-text-secondary);
	font-family: var(--ql-font-mono);
	font-size: 0.75rem;
	overflow-x: auto;
	white-space: nowrap;
}

.external-clients-panel__copy {
	flex-shrink: 0;
	padding: 7px 12px;
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-sm);
	background: var(--ql-surface);
	font: inherit;
	font-size: 0.75rem;
	color: var(--ql-text-secondary);
	cursor: pointer;
	white-space: nowrap;
	transition: border-color 0.12s ease, color 0.12s ease;
}

.external-clients-panel__copy:hover {
	border-color: var(--ql-border-hover);
	color: var(--ql-text);
}
</style>
