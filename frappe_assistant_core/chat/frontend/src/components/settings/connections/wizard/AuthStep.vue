<template>
	<div class="auth-step" data-test="auth-step">
		<div class="auth-step__verdict">
			<span class="auth-step__seal" aria-hidden="true">
				<svg viewBox="0 0 14 14" class="auth-step__seal-glyph">
					<path d="M3.2 7.4 5.9 10.1 10.9 4.4" />
				</svg>
			</span>
			<div class="auth-step__identity">
				<h3 class="auth-step__title" data-test="auth-server-name">
					<strong class="auth-step__name">{{ verdictLead }}</strong> looks good — it needs
					you to sign in.
				</h3>
				<p v-if="identityMeta" class="auth-step__meta">{{ identityMeta }}</p>
			</div>
		</div>

		<dl class="auth-step__facts">
			<div class="auth-step__fact">
				<dt class="auth-step__key">Authorization server</dt>
				<dd class="auth-step__value" data-test="auth-server">
					{{ auth.authorization_server || "Not advertised" }}
				</dd>
			</div>
			<div class="auth-step__fact">
				<dt class="auth-step__key">Scopes requested</dt>
				<dd class="auth-step__value auth-step__scopes" data-test="auth-scopes">
					<span v-for="scope in scopes" :key="scope" class="auth-step__scope">
						{{ scope }}
					</span>
					<span v-if="!scopes.length" class="auth-step__none">None requested</span>
				</dd>
			</div>
		</dl>

		<!-- The question this branch answers is "can we send them to sign in?",
		     and only the presence of a link answers it. `auth.supports_dcr` is a
		     fixed fact about the server, so keying off it stranded every non-DCR
		     server on the form even after AR had built a real authorize URL. -->
		<button
			v-if="authorizeUrl"
			type="button"
			class="auth-step__connect"
			data-test="connect"
			:disabled="busy"
			@click="$emit('connect')"
		>
			<span v-if="busy" class="auth-step__spinner" aria-hidden="true"></span>
			{{ connectLabel }}
			<svg v-if="!busy" viewBox="0 0 14 14" class="auth-step__connect-glyph" aria-hidden="true">
				<path d="M5.2 8.8 9.6 4.4M5.8 4.2h4v4" />
			</svg>
		</button>

		<ManualClientFields
			v-else
			:server-label="serverLabel"
			:submit-label="connectLabel"
			:redirect-uri="redirectUri"
			:busy="busy"
			@credentials="$emit('credentials', $event)"
		/>
	</div>
</template>

<script setup>
import { computed } from "vue";
import ManualClientFields from "./ManualClientFields.vue";

const props = defineProps({
	serverInfo: { type: Object, default: () => ({}) },
	auth: { type: Object, default: () => ({}) },
	redirectUri: { type: String, default: "" },
	authorizeUrl: { type: String, default: "" },
	busy: { type: Boolean, default: false },
});

defineEmits(["connect", "credentials"]);

const serverLabel = computed(() => props.serverInfo?.name || "this server");

// Same name, sentence-initial: the verdict headline opens with it.
const verdictLead = computed(() => props.serverInfo?.name || "This server");

// What the probe read back off `initialize` — the user's confirmation that the
// URL they pasted is the server they meant.
const identityMeta = computed(() => {
	const parts = [];
	if (props.serverInfo?.version) parts.push(`v${props.serverInfo.version}`);
	if (props.serverInfo?.protocol_version) parts.push(`MCP ${props.serverInfo.protocol_version}`);
	return parts.join(" · ");
});

const scopes = computed(() => props.auth?.scopes || []);

const connectLabel = computed(() => (props.busy ? "Opening…" : `Connect to ${serverLabel.value}`));
</script>

<style scoped>
.auth-step {
	display: flex;
	flex-direction: column;
	gap: var(--ql-space-4);
}

.auth-step__verdict {
	display: flex;
	align-items: flex-start;
	gap: 0.625rem;
}

.auth-step__seal {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	flex: none;
	width: 1.5rem;
	height: 1.5rem;
	margin-top: 0.0625rem;
	border-radius: 50%;
	color: var(--ql-success);
	background: color-mix(in srgb, var(--ql-success) 14%, transparent);
}

.auth-step__seal-glyph {
	width: 0.875rem;
	height: 0.875rem;
	fill: none;
	stroke: currentColor;
	stroke-width: 1.8;
	stroke-linecap: round;
	stroke-linejoin: round;
}

.auth-step__identity {
	min-width: 0;
}

.auth-step__title {
	margin: 0;
	font-size: 1.0625rem;
	font-weight: 400;
	line-height: 1.35;
	letter-spacing: -0.01em;
	text-wrap: pretty;
	color: var(--ql-text-secondary);
}

.auth-step__name {
	font-weight: 600;
	color: var(--ql-text);
	word-break: break-word;
}

.auth-step__meta {
	margin: 0.25rem 0 0;
	font-family: var(--ql-font-mono);
	font-size: 0.6875rem;
	letter-spacing: 0.01em;
	color: var(--ql-text-muted);
}

.auth-step__facts {
	display: flex;
	flex-direction: column;
	gap: 0.625rem;
	margin: 0;
	padding: 0.75rem 0.875rem;
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-md);
	background: var(--ql-subtle);
}

.auth-step__fact {
	display: flex;
	flex-direction: column;
	gap: 0.1875rem;
	min-width: 0;
}

.auth-step__key {
	font-size: 0.625rem;
	font-weight: 600;
	letter-spacing: 0.07em;
	text-transform: uppercase;
	color: var(--ql-text-muted);
}

.auth-step__value {
	margin: 0;
	font-size: 0.8125rem;
	color: var(--ql-text);
	word-break: break-all;
}

.auth-step__scopes {
	display: flex;
	flex-wrap: wrap;
	gap: 0.3125rem;
}

.auth-step__scope {
	padding: 0.0625rem 0.4375rem;
	border-radius: 9999px;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	font-family: var(--ql-font-mono);
	font-size: 0.6875rem;
	color: var(--ql-text-secondary);
}

.auth-step__none {
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
}

.auth-step__connect {
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

.auth-step__connect:hover:not(:disabled) {
	background: var(--ql-accent-hover);
	border-color: var(--ql-accent-hover);
}

.auth-step__connect:disabled {
	opacity: 0.55;
	cursor: default;
}

.auth-step__connect-glyph {
	width: 0.875rem;
	height: 0.875rem;
	fill: none;
	stroke: currentColor;
	stroke-width: 1.6;
	stroke-linecap: round;
	stroke-linejoin: round;
}

.auth-step__spinner {
	width: 0.75rem;
	height: 0.75rem;
	border: 2px solid color-mix(in srgb, currentColor 35%, transparent);
	border-top-color: currentColor;
	border-radius: 50%;
	animation: auth-step-spin 0.8s linear infinite;
}

@keyframes auth-step-spin {
	to {
		transform: rotate(360deg);
	}
}

@media (prefers-reduced-motion: reduce) {
	.auth-step__spinner {
		animation-name: none;
	}
}
</style>
