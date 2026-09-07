<template>
	<div class="chunk-card">
		<div class="chunk-meta">
			<span class="chunk-ordinal">Chunk {{ chunk.chunk_index + 1 }}</span>
			<span class="chunk-tokens">{{ chunk.token_count }} tokens</span>
			<span class="chunk-id" :title="chunk.chunk_id">{{ chunk.chunk_id }}</span>
			<button
				class="chunk-copy-btn"
				:title="copied ? 'Copied' : 'Copy text'"
				@click="copyText"
			>
				{{ copied ? "Copied" : "Copy" }}
			</button>
		</div>
		<p class="chunk-text">{{ chunk.chunk_text }}</p>
	</div>
</template>

<script setup>
import { ref } from "vue";

const props = defineProps({
	chunk: { type: Object, required: true },
});

const copied = ref(false);

async function copyText() {
	try {
		await navigator.clipboard.writeText(props.chunk.chunk_text);
		copied.value = true;
		setTimeout(() => (copied.value = false), 1500);
	} catch {
		copied.value = false;
	}
}
</script>

<style scoped>
.chunk-card {
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	padding: 0.875rem 1rem;
	background: var(--ql-surface);
	margin-bottom: 0.75rem;
}

.chunk-meta {
	display: flex;
	align-items: center;
	gap: 0.625rem;
	margin-bottom: 0.5rem;
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
}

.chunk-ordinal {
	font-weight: 600;
	color: var(--ql-text);
}

.chunk-id {
	font-family: "SF Mono", "Fira Code", "Consolas", monospace;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
	max-width: 12rem;
}

.chunk-copy-btn {
	margin-left: auto;
	border: 1px solid var(--ql-border);
	background: none;
	color: var(--ql-text-muted);
	border-radius: 0.375rem;
	padding: 0.125rem 0.5rem;
	font-size: 0.6875rem;
	cursor: pointer;
	transition: all 0.15s ease;
}
.chunk-copy-btn:hover {
	color: var(--ql-text);
	background: var(--ql-subtle);
}

.chunk-text {
	margin: 0;
	font-size: 0.8125rem;
	line-height: 1.6;
	color: var(--ql-text);
	white-space: pre-wrap;
	word-wrap: break-word;
}
</style>
