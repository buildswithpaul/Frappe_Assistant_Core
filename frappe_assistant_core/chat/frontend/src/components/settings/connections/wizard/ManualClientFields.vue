<template>
	<div class="manual-client" data-test="manual-panel">
		<p class="manual-client__hint">
			{{ serverLabel }} doesn't register clients automatically. Register this redirect URI with
			it, then paste back the credentials it gives you.
		</p>

		<div class="manual-client__uri-row">
			<code class="manual-client__uri" data-test="redirect-uri">{{ redirectUri }}</code>
			<button
				type="button"
				class="manual-client__copy"
				data-test="copy-redirect"
				@click="copyRedirect"
			>
				{{ copied ? "Copied" : "Copy" }}
			</button>
		</div>

		<label class="manual-client__field">
			<span class="manual-client__label">Client ID</span>
			<input
				v-model="clientId"
				data-test="client-id"
				type="text"
				class="manual-client__input"
				autocomplete="off"
			/>
		</label>

		<label class="manual-client__field">
			<span class="manual-client__label">Client secret</span>
			<input
				v-model="clientSecret"
				data-test="client-secret"
				type="password"
				class="manual-client__input"
				autocomplete="off"
			/>
			<span class="manual-client__note">Leave blank for a public client.</span>
		</label>

		<p v-if="error" class="manual-client__error" role="alert" data-test="auth-error">
			{{ error }}
		</p>

		<button
			type="button"
			class="manual-client__submit"
			data-test="submit-credentials"
			:disabled="busy"
			@click="submit"
		>
			<span v-if="busy" class="manual-client__spinner" aria-hidden="true"></span>
			{{ submitLabel }}
		</button>
	</div>
</template>

<script setup>
import { ref } from "vue";

const props = defineProps({
	serverLabel: { type: String, default: "this server" },
	submitLabel: { type: String, default: "" },
	redirectUri: { type: String, default: "" },
	busy: { type: Boolean, default: false },
});

const emit = defineEmits(["credentials"]);

const clientId = ref("");
const clientSecret = ref("");
const error = ref("");
const copied = ref(false);

async function copyRedirect() {
	try {
		await navigator.clipboard.writeText(props.redirectUri);
		copied.value = true;
		setTimeout(() => (copied.value = false), 1500);
	} catch {
		copied.value = false;
	}
}

function submit() {
	// Validate the exact strings about to be emitted, not the raw refs — a
	// whitespace-only client ID must not reach AR as a manual registration.
	const id = clientId.value.trim();
	if (!id) {
		error.value = "Paste the client ID this server gave you.";
		return;
	}
	error.value = "";
	emit("credentials", { client_id: id, client_secret: clientSecret.value.trim() });
}
</script>

<style scoped>
.manual-client {
	display: flex;
	flex-direction: column;
	gap: 0.75rem;
	padding: 0.875rem;
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-md);
	background: var(--ql-subtle);
}

.manual-client__hint {
	margin: 0;
	font-size: 0.75rem;
	line-height: 1.5;
	text-wrap: pretty;
	color: var(--ql-text-secondary);
}

.manual-client__uri-row {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.375rem 0.375rem 0.375rem 0.625rem;
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-sm);
	background: var(--ql-surface);
}

.manual-client__uri {
	flex: 1;
	min-width: 0;
	font-family: var(--ql-font-mono);
	font-size: 0.6875rem;
	color: var(--ql-text);
	word-break: break-all;
}

.manual-client__copy {
	flex: none;
	padding: 0.25rem 0.5rem;
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-sm);
	background: var(--ql-bg);
	font: inherit;
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-accent);
	cursor: pointer;
	white-space: nowrap;
}

.manual-client__copy:hover {
	border-color: var(--ql-border-hover);
}

.manual-client__field {
	display: flex;
	flex-direction: column;
	gap: 0.3125rem;
}

.manual-client__label {
	font-size: 0.625rem;
	font-weight: 600;
	letter-spacing: 0.07em;
	text-transform: uppercase;
	color: var(--ql-text-muted);
}

.manual-client__input {
	padding: 0.5rem 0.625rem;
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-sm);
	background: var(--ql-surface);
	color: var(--ql-text);
	font: inherit;
	font-size: 0.8125rem;
	outline: none;
}

.manual-client__input:focus {
	border-color: var(--ql-accent);
	box-shadow: 0 0 0 3px var(--ql-accent-soft);
}

.manual-client__note {
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
}

.manual-client__error {
	margin: 0;
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-danger);
}

.manual-client__submit {
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

.manual-client__submit:hover:not(:disabled) {
	background: var(--ql-accent-hover);
	border-color: var(--ql-accent-hover);
}

.manual-client__submit:disabled {
	opacity: 0.55;
	cursor: default;
}

.manual-client__spinner {
	width: 0.75rem;
	height: 0.75rem;
	border: 2px solid color-mix(in srgb, currentColor 35%, transparent);
	border-top-color: currentColor;
	border-radius: 50%;
	animation: manual-client-spin 0.8s linear infinite;
}

@keyframes manual-client-spin {
	to {
		transform: rotate(360deg);
	}
}

@media (prefers-reduced-motion: reduce) {
	.manual-client__spinner {
		animation-name: none;
	}
}
</style>
