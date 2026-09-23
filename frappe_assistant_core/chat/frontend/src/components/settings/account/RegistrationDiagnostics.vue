<template>
	<div class="diagnostics-card">
		<div class="diag-header">
			<div>
				<h4 class="diag-title">Registration health</h4>
				<p class="diag-subtitle">Verify that this site can talk to FAC Cloud.</p>
			</div>
			<button type="button" class="run-btn" :disabled="running" @click="runDiagnostics">
				<svg v-if="running" class="spinner" viewBox="0 0 24 24" aria-hidden="true">
					<circle
						cx="12"
						cy="12"
						r="10"
						stroke="currentColor"
						stroke-width="3"
						fill="none"
						opacity="0.25"
					/>
					<path
						d="M12 2a10 10 0 0 1 10 10"
						stroke="currentColor"
						stroke-width="3"
						fill="none"
						stroke-linecap="round"
					/>
				</svg>
				<span>{{ running ? "Running…" : "Run diagnostics" }}</span>
			</button>
		</div>

		<!-- Empty / initial state -->
		<p v-if="!result && !error" class="empty-hint">
			Click <strong>Run diagnostics</strong> to check this site's connection and origin
			binding against FAC Cloud.
		</p>

		<!-- Network-level error from the API call itself -->
		<div v-else-if="error" class="result-banner banner-error">
			<svg
				class="banner-icon"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				aria-hidden="true"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
				/>
			</svg>
			<div class="banner-body">
				<p class="banner-title">Couldn't reach FAC Cloud</p>
				<p class="banner-text">{{ error }}</p>
			</div>
		</div>

		<!-- status === "ok" — site is correctly bound -->
		<div v-else-if="result.status === 'ok'" class="result-banner banner-success">
			<svg
				class="banner-icon"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				aria-hidden="true"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M5 13l4 4L19 7"
				/>
			</svg>
			<div class="banner-body">
				<p class="banner-title">All good</p>
				<p class="banner-text">
					Bound to <code>{{ result.bound_host || "—" }}</code>
					<template v-if="result.last_verification">
						· last verified
						<time :datetime="result.last_verification">{{
							formatTimestamp(result.last_verification)
						}}</time>
					</template>
				</p>
			</div>
		</div>

		<!-- status === "origin_mismatch" — claimed host ≠ bound host -->
		<div v-else-if="result.status === 'origin_mismatch'" class="result-banner banner-error">
			<svg
				class="banner-icon"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				aria-hidden="true"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
				/>
			</svg>
			<div class="banner-body">
				<p class="banner-title">Origin mismatch</p>
				<p class="banner-text">
					This site is bound to
					<code>{{ result.bound_host || "(none)" }}</code> on FAC Cloud, but it's running at
					<code>{{ result.claimed_host || "(unknown)" }}</code
					>. Re-bind to rotate the secret to this URL.
				</p>
				<button type="button" class="remediation-btn" @click="$emit('open-rebind')">
					Re-register / rotate secret
				</button>
			</div>
		</div>

		<!-- status === "callback_failed" — AR couldn't reach this site -->
		<div v-else-if="result.status === 'callback_failed'" class="result-banner banner-warn">
			<svg
				class="banner-icon"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				aria-hidden="true"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
				/>
			</svg>
			<div class="banner-body">
				<p class="banner-title">FAC Cloud couldn't reach this site</p>
				<p class="banner-text">
					FAC Cloud tried to call back to
					<code>{{ result.bound_host || "this site" }}</code> and failed. Check the
					site's network, DNS, and firewall rules.
				</p>
			</div>
		</div>

		<!-- status === "no_client" — local config missing -->
		<div v-else-if="result.status === 'no_client'" class="result-banner banner-warn">
			<svg
				class="banner-icon"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				aria-hidden="true"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
				/>
			</svg>
			<div class="banner-body">
				<p class="banner-title">No FAC Cloud client configured</p>
				<p class="banner-text">
					This site has no tenant credentials yet. Complete registration first.
				</p>
			</div>
		</div>

		<!-- Unknown status — show the raw payload for debugging -->
		<div v-else class="result-banner banner-warn">
			<svg
				class="banner-icon"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				aria-hidden="true"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
				/>
			</svg>
			<div class="banner-body">
				<p class="banner-title">Unexpected response</p>
				<pre class="raw-result">{{ JSON.stringify(result, null, 2) }}</pre>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref } from "vue";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";

defineEmits(["open-rebind"]);

const running = ref(false);
const result = ref(null);
const error = ref(null);

async function runDiagnostics() {
	running.value = true;
	error.value = null;
	try {
		const r = await api.registration.runDiagnostics();
		result.value = r || { status: "unknown" };
	} catch (err) {
		logger.error("Diagnostics failed", err);
		error.value =
			err?.userMessage || err?.message || "Couldn't run diagnostics. Please try again.";
		result.value = null;
	} finally {
		running.value = false;
	}
}

function formatTimestamp(ts) {
	try {
		return new Date(ts).toLocaleString();
	} catch {
		return ts;
	}
}

defineExpose({ runDiagnostics });
</script>

<style scoped>
.diagnostics-card {
	display: flex;
	flex-direction: column;
	gap: 1rem;
	padding: 1rem;
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
}

.diag-header {
	display: flex;
	justify-content: space-between;
	align-items: flex-start;
	gap: 1rem;
}

.diag-title {
	margin: 0 0 0.25rem;
	font-size: 0.9375rem;
	font-weight: 600;
	color: var(--ql-text);
}

.diag-subtitle {
	margin: 0;
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
}

.run-btn {
	display: inline-flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.5rem 1rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: white;
	background: var(--ql-accent);
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
	white-space: nowrap;
}

.run-btn:hover:not(:disabled) {
	opacity: 0.92;
}

.run-btn:disabled {
	opacity: 0.6;
	cursor: not-allowed;
}

.spinner {
	width: 0.875rem;
	height: 0.875rem;
	animation: spin 0.8s linear infinite;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

.empty-hint {
	margin: 0;
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
	line-height: 1.5;
}

.empty-hint strong {
	color: var(--ql-text);
}

.result-banner {
	display: flex;
	gap: 0.75rem;
	padding: 0.875rem 1rem;
	border-radius: 0.5rem;
	border: 1px solid transparent;
}

.banner-success {
	background: rgba(34, 197, 94, 0.08);
	border-color: rgba(34, 197, 94, 0.25);
	color: #16a34a;
}

.banner-error {
	background: rgba(239, 68, 68, 0.08);
	border-color: rgba(239, 68, 68, 0.25);
	color: #b91c1c;
}

.banner-warn {
	background: rgba(234, 179, 8, 0.08);
	border-color: rgba(234, 179, 8, 0.25);
	color: #a16207;
}

.banner-icon {
	width: 1.25rem;
	height: 1.25rem;
	flex-shrink: 0;
	margin-top: 0.125rem;
}

.banner-body {
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
	min-width: 0;
}

.banner-title {
	margin: 0;
	font-size: 0.875rem;
	font-weight: 600;
}

.banner-text {
	margin: 0;
	font-size: 0.8125rem;
	color: var(--ql-text);
	line-height: 1.5;
	word-break: break-word;
}

.banner-text code {
	padding: 0.0625rem 0.375rem;
	font-family: monospace;
	font-size: 0.75rem;
	background: var(--ql-subtle);
	border-radius: 0.25rem;
	color: var(--ql-text);
}

.remediation-btn {
	align-self: flex-start;
	padding: 0.4375rem 0.875rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: white;
	background: var(--ql-danger, #ef4444);
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
}

.remediation-btn:hover {
	background: #dc2626;
}

.raw-result {
	margin: 0;
	padding: 0.5rem;
	font-family: monospace;
	font-size: 0.6875rem;
	color: var(--ql-text);
	background: var(--ql-subtle);
	border-radius: 0.375rem;
	overflow-x: auto;
}
</style>
