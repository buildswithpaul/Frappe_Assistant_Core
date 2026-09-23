<template>
	<Teleport to="body">
		<div v-if="isOpen" class="modal-overlay" @click.self="handleOverlayClick">
			<div class="rebind-modal" role="dialog" aria-modal="true">
				<button type="button" class="close-btn" aria-label="Close" @click="handleClose">
					&times;
				</button>

				<!-- Step indicator -->
				<div class="step-indicator" aria-hidden="true">
					<span :class="['step', { active: step >= 1, done: step > 1 }]">1</span>
					<span class="step-line"></span>
					<span :class="['step', { active: step >= 2, done: step > 2 }]">2</span>
					<span class="step-line"></span>
					<span :class="['step', { active: step >= 3 }]">3</span>
				</div>

				<!-- Step 1: Initiate rebind -->
				<template v-if="step === 1">
					<h3 class="modal-title">Rotate tenant secret</h3>
					<p class="modal-description">
						Rebinding rotates this site's tenant secret and updates the bound URL on
						FAC Cloud. Useful when the site moved to a new URL or you suspect
						the current secret was leaked.
					</p>

					<label class="field-label" for="rebind-site-url">Site URL</label>
					<input
						id="rebind-site-url"
						v-model.trim="newSiteUrl"
						type="url"
						class="site-input"
						:class="{ 'is-error': initiateError }"
						placeholder="https://your-site.example.com"
						:disabled="initiating"
					/>
					<p class="field-hint">
						Defaults to this site's current URL — keep it as-is for a same-host rotate,
						or change it if you've moved.
					</p>

					<p v-if="initiateError" class="error-text" role="alert">
						{{ initiateError }}
					</p>

					<div class="modal-actions">
						<button
							type="button"
							class="btn btn-secondary"
							:disabled="initiating"
							@click="handleClose"
						>
							Cancel
						</button>
						<button
							type="button"
							class="btn btn-primary"
							:disabled="!canInitiate || initiating"
							@click="initiateRebind"
						>
							<svg
								v-if="initiating"
								class="spinner"
								viewBox="0 0 24 24"
								aria-hidden="true"
							>
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
							<span>{{ initiating ? "Sending…" : "Send rebind email" }}</span>
						</button>
					</div>
				</template>

				<!-- Step 2: Awaiting email confirmation -->
				<template v-else-if="step === 2">
					<h3 class="modal-title">Confirm from your email</h3>
					<p class="modal-description">
						We sent a confirmation link. Open it on the same network the owner controls
						— once you click it, FAC Cloud rotates the secret and we pick it up here
						automatically.
					</p>

					<div class="poll-card">
						<div class="poll-spinner" aria-hidden="true"></div>
						<div class="poll-meta">
							<p class="poll-status">
								<template v-if="pollError">
									Last poll failed — will retry…
								</template>
								<template v-else>
									Waiting for confirmation
									<template v-if="lastPollAt">
										· checked {{ secondsAgo(lastPollAt) }}s ago
									</template>
								</template>
							</p>
							<p class="poll-meta-hint">
								Token expires {{ expiresAtLabel }}. We'll stop polling
								automatically if it does.
							</p>
						</div>
					</div>

					<p v-if="pollTimeoutReached" class="timeout-text" role="alert">
						We didn't see a confirmation in time. The link may have expired or wasn't
						clicked.
					</p>

					<div class="modal-actions">
						<button type="button" class="btn btn-secondary" @click="handleClose">
							Close
						</button>
						<button type="button" class="btn btn-primary" @click="restart">
							Start over
						</button>
					</div>
				</template>

				<!-- Step 3: Done -->
				<template v-else-if="step === 3">
					<div class="success-icon-wrap">
						<svg
							class="success-icon"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M5 13l4 4L19 7"
							/>
						</svg>
					</div>
					<h3 class="modal-title modal-title-success">Secret rotated</h3>
					<p class="modal-description">
						This site is now bound to
						<code>{{ confirmedSiteUrl }}</code> on FAC Cloud. You can close
						this dialog.
					</p>

					<div class="modal-actions modal-actions-single">
						<button type="button" class="btn btn-primary" @click="handleDone">
							Done
						</button>
					</div>
				</template>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
import { ref, computed, watch, onBeforeUnmount } from "vue";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";

const props = defineProps({
	isOpen: { type: Boolean, default: false },
});

const emit = defineEmits(["close", "rebound"]);

const step = ref(1);
const newSiteUrl = ref("");
const initiating = ref(false);
const initiateError = ref(null);

const pollError = ref(null);
const lastPollAt = ref(null);
const expiresAt = ref(null);
const pollTimeoutReached = ref(false);

let pollTimer = null;
let attemptCount = 0;

// 20 minutes worst case, with exponential backoff capped at 30s. The token
// itself expires after 15 minutes on the server; we keep polling for a few
// extra minutes to cover clock skew + last-second clicks.
const MAX_POLL_MS = 20 * 60 * 1000;
const POLL_BASE_MS = 5000; // 5s initial cadence
const POLL_MAX_MS = 30000; // 30s ceiling
const pollStartedAt = ref(null);

const confirmedSiteUrl = ref("");

const canInitiate = computed(() => isValidUrl(newSiteUrl.value));
const expiresAtLabel = computed(() => {
	if (!expiresAt.value) return "shortly";
	try {
		return `at ${new Date(expiresAt.value).toLocaleTimeString()}`;
	} catch {
		return "shortly";
	}
});

function isValidUrl(value) {
	if (!value) return false;
	try {
		const u = new URL(value);
		return ["http:", "https:"].includes(u.protocol) && !!u.hostname;
	} catch {
		return false;
	}
}

function secondsAgo(ts) {
	return Math.max(0, Math.round((Date.now() - ts) / 1000));
}

watch(
	() => props.isOpen,
	(open) => {
		if (open) reset(/* prefillSiteUrl */ true);
		else stopPolling();
	}
);

onBeforeUnmount(stopPolling);

function reset(prefillSiteUrl = false) {
	step.value = 1;
	initiateError.value = null;
	pollError.value = null;
	pollTimeoutReached.value = false;
	lastPollAt.value = null;
	expiresAt.value = null;
	confirmedSiteUrl.value = "";
	attemptCount = 0;
	pollStartedAt.value = null;
	if (prefillSiteUrl) {
		newSiteUrl.value = window.location.origin;
	}
}

function restart() {
	stopPolling();
	reset(true);
}

async function initiateRebind() {
	if (!canInitiate.value) return;
	initiating.value = true;
	initiateError.value = null;
	try {
		const result = await api.registration.requestSiteRebind(newSiteUrl.value);
		if (!result?.success) {
			initiateError.value = result?.error || "Couldn't request rebind. Please try again.";
			return;
		}
		expiresAt.value = result.expires_at || null;
		confirmedSiteUrl.value = newSiteUrl.value;
		step.value = 2;
		startPolling();
	} catch (err) {
		logger.error("requestSiteRebind failed", err);
		initiateError.value =
			err?.userMessage || err?.message || "Couldn't reach the server. Please try again.";
	} finally {
		initiating.value = false;
	}
}

function startPolling() {
	stopPolling();
	pollStartedAt.value = Date.now();
	attemptCount = 0;
	pollOnce();
}

function stopPolling() {
	if (pollTimer) {
		clearTimeout(pollTimer);
		pollTimer = null;
	}
}

async function pollOnce() {
	if (!props.isOpen || step.value !== 2) return;
	if (Date.now() - pollStartedAt.value > MAX_POLL_MS) {
		pollTimeoutReached.value = true;
		stopPolling();
		return;
	}

	try {
		const result = await api.registration.pollForRotatedSecret();
		lastPollAt.value = Date.now();
		pollError.value = null;
		if (result?.success) {
			stopPolling();
			step.value = 3;
			emit("rebound");
			return;
		}
		// Result without success === secret not ready yet. That's the
		// expected path until the owner clicks; keep polling silently.
	} catch (err) {
		logger.warn("pollForRotatedSecret transient failure", err);
		pollError.value = err?.userMessage || err?.message || "Network error";
		lastPollAt.value = Date.now();
	}

	attemptCount += 1;
	// Exponential backoff: 5s, 7s, ~10s, ~14s, ~20s, 30s (cap).
	// Caps total calls at ~50 over 20 minutes instead of 240.
	const delay = Math.min(POLL_BASE_MS * Math.pow(1.4, attemptCount), POLL_MAX_MS);
	pollTimer = setTimeout(pollOnce, delay);
}

function handleClose() {
	stopPolling();
	emit("close");
}

function handleOverlayClick() {
	// Mid-flow overlay clicks shouldn't accidentally cancel a pending rebind —
	// require an explicit Close press once step 1 is past.
	if (step.value === 1) emit("close");
}

function handleDone() {
	stopPolling();
	emit("close");
}
</script>

<style scoped>
.modal-overlay {
	position: fixed;
	inset: 0;
	background: rgba(0, 0, 0, 0.5);
	display: flex;
	align-items: center;
	justify-content: center;
	z-index: 1100;
	padding: 1rem;
}

.rebind-modal {
	position: relative;
	background: var(--ql-surface, #fff);
	border-radius: 0.75rem;
	padding: 1.75rem;
	max-width: 480px;
	width: 100%;
	box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.15), 0 10px 10px -5px rgba(0, 0, 0, 0.05);
}

.close-btn {
	position: absolute;
	top: 0.5rem;
	right: 0.75rem;
	width: 2rem;
	height: 2rem;
	font-size: 1.5rem;
	line-height: 1;
	color: var(--ql-text-muted);
	background: transparent;
	border: none;
	cursor: pointer;
	border-radius: 0.375rem;
}

.close-btn:hover {
	background: var(--ql-subtle);
	color: var(--ql-text);
}

.step-indicator {
	display: flex;
	align-items: center;
	justify-content: center;
	gap: 0.5rem;
	margin-bottom: 1.25rem;
}

.step {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	width: 1.75rem;
	height: 1.75rem;
	font-size: 0.8125rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 50%;
}

.step.active {
	color: white;
	background: var(--ql-accent);
	border-color: var(--ql-accent);
}

.step.done {
	color: white;
	background: var(--ql-success, #22c55e);
	border-color: var(--ql-success, #22c55e);
}

.step-line {
	flex: 0 0 2.5rem;
	height: 2px;
	background: var(--ql-border);
}

.modal-title {
	margin: 0 0 0.5rem;
	font-size: 1.125rem;
	font-weight: 600;
	color: var(--ql-text);
}

.modal-title-success {
	color: var(--ql-success, #22c55e);
}

.modal-description {
	margin: 0 0 1.25rem;
	font-size: 0.875rem;
	color: var(--ql-text-muted);
	line-height: 1.5;
}

.modal-description code {
	padding: 0.0625rem 0.375rem;
	font-family: monospace;
	font-size: 0.75rem;
	background: var(--ql-subtle);
	border-radius: 0.25rem;
	color: var(--ql-text);
}

.field-label {
	display: block;
	margin-bottom: 0.375rem;
	font-size: 0.75rem;
	font-weight: 600;
	text-transform: uppercase;
	letter-spacing: 0.05em;
	color: var(--ql-text-muted);
}

.site-input {
	width: 100%;
	padding: 0.625rem 0.75rem;
	font-size: 0.875rem;
	font-family: monospace;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	outline: none;
}

.site-input:focus {
	border-color: var(--ql-accent);
	box-shadow: 0 0 0 3px var(--ql-accent-soft);
}

.site-input.is-error {
	border-color: var(--ql-danger, #ef4444);
}

.field-hint {
	margin: 0.375rem 0 0;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	line-height: 1.4;
}

.error-text {
	margin: 0.75rem 0 0;
	font-size: 0.8125rem;
	color: var(--ql-danger, #ef4444);
	line-height: 1.5;
}

.poll-card {
	display: flex;
	align-items: center;
	gap: 0.875rem;
	padding: 1rem;
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
}

.poll-spinner {
	flex: 0 0 1.5rem;
	width: 1.5rem;
	height: 1.5rem;
	border: 3px solid var(--ql-border);
	border-top-color: var(--ql-accent);
	border-radius: 50%;
	animation: spin 0.8s linear infinite;
}

.poll-meta {
	display: flex;
	flex-direction: column;
	gap: 0.25rem;
	min-width: 0;
}

.poll-status {
	margin: 0;
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
}

.poll-meta-hint {
	margin: 0;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	line-height: 1.4;
}

.timeout-text {
	margin: 0.75rem 0 0;
	font-size: 0.8125rem;
	color: var(--ql-danger, #ef4444);
	line-height: 1.5;
}

.success-icon-wrap {
	display: flex;
	justify-content: center;
	margin-bottom: 1rem;
}

.success-icon {
	width: 3rem;
	height: 3rem;
	color: var(--ql-success, #22c55e);
	background: rgba(34, 197, 94, 0.1);
	border-radius: 50%;
	padding: 0.5rem;
}

.modal-actions {
	display: flex;
	justify-content: flex-end;
	gap: 0.75rem;
	margin-top: 1.5rem;
}

.modal-actions-single {
	justify-content: center;
}

.btn {
	display: inline-flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.5rem 1.25rem;
	font-size: 0.875rem;
	font-weight: 500;
	border-radius: 0.375rem;
	cursor: pointer;
	transition: opacity 0.15s ease, background 0.15s ease;
	border: 1px solid transparent;
}

.btn:disabled {
	opacity: 0.6;
	cursor: not-allowed;
}

.btn-primary {
	color: white;
	background: var(--ql-accent);
}

.btn-primary:hover:not(:disabled) {
	opacity: 0.92;
}

.btn-secondary {
	color: var(--ql-text);
	background: var(--ql-bg);
	border-color: var(--ql-border);
}

.btn-secondary:hover:not(:disabled) {
	background: var(--ql-subtle);
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
</style>
