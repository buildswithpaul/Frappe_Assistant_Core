<template>
	<form class="entry-step" @submit.prevent="submit">
		<div class="entry-step__intro">
			<h3 class="entry-step__title">Add a connection</h3>
			<p class="entry-step__lede">
				Paste an MCP server's endpoint. We check it before anything is saved.
			</p>
		</div>

		<label class="entry-step__field">
			<span class="entry-step__label">Endpoint URL</span>
			<input
				v-model="endpointUrl"
				data-test="endpoint-url"
				type="text"
				class="entry-step__input"
				placeholder="https://example.com/mcp"
				autocomplete="off"
			/>
		</label>

		<p class="entry-step__hint">
			Must be a Streamable HTTP MCP endpoint. SSE-only servers are not supported yet.
		</p>

		<button type="submit" class="entry-step__submit" data-test="check" :disabled="busy">
			<span v-if="busy" class="entry-step__spinner" aria-hidden="true"></span>
			{{ busy ? "Checking…" : "Check this server" }}
		</button>
	</form>
</template>

<script setup>
import { ref } from "vue";

const props = defineProps({
	busy: { type: Boolean, default: false },
	initialUrl: { type: String, default: "" },
});

const emit = defineEmits(["check"]);

const endpointUrl = ref(props.initialUrl);

// Validation stays with the parent, next to the one `error` slot this screen
// shares with the manual-credentials retry path — this component only trims
// and hands the raw string up, so there is never a second, child-owned error
// message competing with a leftover one the parent is still showing.
function submit() {
	emit("check", endpointUrl.value.trim());
}
</script>

<style scoped>
.entry-step {
	display: flex;
	flex-direction: column;
	gap: var(--ql-space-4);
}

.entry-step__intro {
	display: flex;
	flex-direction: column;
	gap: 0.25rem;
}

.entry-step__title {
	margin: 0;
	font-size: 1.0625rem;
	font-weight: 600;
	line-height: 1.3;
	letter-spacing: -0.01em;
	color: var(--ql-text);
}

.entry-step__lede {
	margin: 0;
	font-size: 0.8125rem;
	line-height: 1.5;
	text-wrap: pretty;
	color: var(--ql-text-secondary);
}

.entry-step__field {
	display: flex;
	flex-direction: column;
	gap: 0.3125rem;
	margin-bottom: -0.625rem;
}

.entry-step__label {
	font-size: 0.625rem;
	font-weight: 600;
	letter-spacing: 0.07em;
	text-transform: uppercase;
	color: var(--ql-text-muted);
}

.entry-step__input {
	padding: 0.625rem 0.75rem;
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-md);
	background: var(--ql-bg);
	color: var(--ql-text);
	font-family: var(--ql-font-mono);
	font-size: 0.8125rem;
	outline: none;
}

.entry-step__input::placeholder {
	color: var(--ql-text-muted);
}

.entry-step__input:focus {
	border-color: var(--ql-accent);
	box-shadow: 0 0 0 3px var(--ql-accent-soft);
}

.entry-step__hint {
	margin: 0;
	font-size: 0.6875rem;
	line-height: 1.5;
	text-wrap: pretty;
	color: var(--ql-text-muted);
}

.entry-step__submit {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	gap: 0.4375rem;
	width: 100%;
	padding: 0.625rem 1rem;
	border: 1px solid var(--ql-accent);
	border-radius: var(--ql-radius-md);
	background: var(--ql-accent);
	color: var(--ql-bg);
	font: inherit;
	font-size: 0.875rem;
	font-weight: 600;
	cursor: pointer;
}

.entry-step__submit:hover:not(:disabled) {
	background: var(--ql-accent-hover);
	border-color: var(--ql-accent-hover);
}

.entry-step__submit:disabled {
	opacity: 0.55;
	cursor: default;
}

.entry-step__spinner {
	width: 0.75rem;
	height: 0.75rem;
	border: 2px solid color-mix(in srgb, currentColor 35%, transparent);
	border-top-color: currentColor;
	border-radius: 50%;
	animation: entry-step-spin 0.8s linear infinite;
}

@keyframes entry-step-spin {
	to {
		transform: rotate(360deg);
	}
}

@media (prefers-reduced-motion: reduce) {
	.entry-step__spinner {
		animation-name: none;
	}
}
</style>
