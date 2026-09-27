<template>
	<div class="reconnect-card" data-test="reconnect-card">
		<h2 class="reconnect-title">Reconnect this site</h2>
		<p class="reconnect-text">
			We'll email a verification link to
			<strong>{{ ownerEmailMasked }}</strong>. Click it to finish reconnecting.
		</p>
		<button
			class="reconnect-btn"
			data-test="reconnect-send"
			:disabled="sending"
			@click="$emit('send')"
		>
			<span v-if="!sending">Send verification email</span>
			<span v-else>Sending…</span>
		</button>
	</div>
</template>

<script setup>
defineProps({
	ownerEmailMasked: { type: String, default: "" },
	sending: { type: Boolean, default: false },
});

defineEmits(["send"]);
</script>

<style scoped>
.reconnect-card {
	max-width: 400px;
	padding: 2rem;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	text-align: center;
}

.reconnect-title {
	font-size: 1.25rem;
	font-weight: 600;
	color: var(--ql-text);
	margin-bottom: 0.75rem;
}

.reconnect-text {
	font-size: 0.875rem;
	color: var(--ql-text-muted);
	margin-bottom: 1.25rem;
	line-height: 1.5;
}

.reconnect-text strong {
	color: var(--ql-text);
}

.reconnect-btn {
	padding: 0.625rem 1.5rem;
	font-size: 0.875rem;
	font-weight: 600;
	color: white;
	background: var(--ql-accent);
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.2s ease;
	min-width: 200px;
}

.reconnect-btn:hover:not(:disabled) {
	transform: translateY(-1px);
}

.reconnect-btn:disabled {
	opacity: 0.7;
	cursor: not-allowed;
}
</style>
