<template>
	<div class="mockup">
		<div class="node">Input</div>
		<div class="edge">→</div>
		<div class="node node-active">Agent</div>
		<div class="edge">→</div>
		<div class="node">Output</div>
	</div>
</template>

<style scoped>
.mockup {
	display: flex; align-items: center; justify-content: center; gap: 10px;
	max-width: 360px; margin: 0 auto;
}
.node {
	padding: 10px 16px;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 10px;
	font-size: 12px;
	font-weight: 600;
	color: var(--ql-text);
}
.node-active {
	background: var(--ql-accent-soft);
	border-color: var(--ql-accent);
	color: var(--ql-accent-hover);
	box-shadow: 0 0 14px var(--ql-accent-soft);
}
.edge {
	color: var(--ql-text-muted);
	font-size: 16px;
	font-weight: 500;
}
</style>
