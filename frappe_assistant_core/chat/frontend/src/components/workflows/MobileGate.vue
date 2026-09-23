<template>
	<div class="mobile-gate">
		<svg
			width="48"
			height="48"
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
			style="opacity: 0.4"
		>
			<path
				stroke-linecap="round"
				stroke-linejoin="round"
				stroke-width="1.5"
				d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
			/>
		</svg>
		<h3>Desktop Required</h3>
		<p>The agent builder works best on screens wider than 768px.</p>
		<button class="back-link" @click="$emit('back')">Back to Agents</button>
	</div>
</template>

<script setup>
defineEmits(["back"]);
</script>

<style scoped>
.mobile-gate {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	height: 100%;
	padding: 2rem;
	text-align: center;
	color: var(--ql-text-muted);
	gap: 0.5rem;
}

.mobile-gate h3 {
	font-size: 1.125rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0;
}

.mobile-gate p {
	font-size: 0.875rem;
	margin: 0;
	max-width: 300px;
}

.back-link {
	margin-top: 1rem;
	padding: 0.5rem 1rem;
	font-size: 0.875rem;
	color: var(--ql-accent);
	background: transparent;
	border: 1px solid var(--ql-accent);
	border-radius: 0.5rem;
	cursor: pointer;
}

.back-link:hover {
	background: var(--ql-accent-soft);
}
</style>
