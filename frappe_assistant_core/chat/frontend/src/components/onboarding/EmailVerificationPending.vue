<template>
	<div class="verification-pending">
		<!-- Mode: awaiting-click — owner just submitted the form -->
		<template v-if="mode === 'awaiting-click'">
			<FacoRobot size="lg" mood="attentive" float show-arms show-shadow extra-class="mb-6" />

			<h1 class="title">Check your email</h1>
			<p class="subtitle">
				We sent a verification link to
				<strong>{{ ownerEmail }}</strong
				>. Click it to finish setting up FACO.
			</p>

			<div class="hint-card">
				<p class="hint">
					The link is valid for 24 hours. If it doesn't arrive, check your spam folder.
				</p>
			</div>

			<div class="actions">
				<button
					type="button"
					class="secondary-btn"
					:disabled="resending"
					@click="onResend"
				>
					<svg v-if="resending" class="spinner" viewBox="0 0 24 24" aria-hidden="true">
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
					<span>{{ resending ? "Resending…" : "Resend email" }}</span>
				</button>
				<button type="button" class="link-btn" @click="changing = !changing">
					Wrong email?
				</button>
			</div>
			<form v-if="changing" class="change-email" @submit.prevent="submitChange">
				<input v-model="newEmail" type="email" required placeholder="Correct email address" />
				<button type="submit" class="secondary-btn">Send to this address</button>
			</form>
			<p v-if="notice" class="resent-toast" role="status">{{ notice }}</p>
		</template>

		<!-- Mode: verifying — landed via deep link, exchanging token for secret -->
		<template v-else-if="mode === 'verifying'">
			<FacoRobot
				size="lg"
				:mood="verifyError ? 'concerned' : 'thinking'"
				float
				show-arms
				show-shadow
				extra-class="mb-6"
			/>

			<template v-if="!verifyError && !verifyDone">
				<h1 class="title">Verifying your site…</h1>
				<p class="subtitle">Activating your tenant. This only takes a moment.</p>
				<div class="big-spinner" aria-hidden="true"></div>
			</template>

			<template v-else-if="verifyDone">
				<div class="success-icon">
					<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M5 13l4 4L19 7"
						/>
					</svg>
				</div>
				<h1 class="title title-success">Tenant active</h1>
				<p class="subtitle">You're all set. Taking you to your chat…</p>
			</template>

			<template v-else>
				<div class="error-card">
					<div class="error-icon">
						<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
							/>
						</svg>
					</div>
					<p class="error-text">{{ verifyError }}</p>
					<button type="button" class="retry-btn" @click="runVerification">
						Try again
					</button>
				</div>
			</template>
		</template>
	</div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { api } from "@/api/client";
import FacoRobot from "@/components/common/FacoRobot.vue";
import { logger } from "@/utils/logger";

const props = defineProps({
	mode: {
		type: String,
		required: true,
		validator: (v) => ["awaiting-click", "verifying"].includes(v),
	},
	ownerEmail: { type: String, default: "" },
	notice: { type: String, default: "" },
	// Only used in mode="verifying": the token from `?verify_token=...`.
	verificationToken: { type: String, default: "" },
});

const emit = defineEmits(["resend", "change-email", "verified", "verify-failed"]);

const resending = ref(false);
const changing = ref(false);
const newEmail = ref("");

const verifyDone = ref(false);
const verifyError = ref(null);

function onResend() {
	if (resending.value) return;
	resending.value = true;
	emit("resend", () => {
		resending.value = false;
	});
}

function submitChange() {
	const address = newEmail.value.trim();
	if (!address) return;
	emit("change-email", address, () => {
		changing.value = false;
		newEmail.value = "";
	});
}

async function runVerification() {
	verifyError.value = null;
	verifyDone.value = false;
	if (!props.verificationToken) {
		verifyError.value = "Missing verification token. Please use the link from your email.";
		emit("verify-failed", verifyError.value);
		return;
	}
	try {
		const result = await api.registration.completeEmailVerification(props.verificationToken);
		if (result?.success) {
			verifyDone.value = true;
			// Brief pause so the user sees the success state before the parent
			// transitions us out.
			setTimeout(() => emit("verified"), 1200);
		} else {
			verifyError.value =
				result?.error || "Couldn't activate your tenant. The link may have expired.";
			emit("verify-failed", verifyError.value);
		}
	} catch (err) {
		logger.error("Email verification failed", err);
		verifyError.value =
			err?.userMessage || err?.message || "Couldn't reach the server. Please try again.";
		emit("verify-failed", verifyError.value);
	}
}

onMounted(() => {
	if (props.mode === "verifying") {
		runVerification();
	}
});
</script>

<style scoped>
.verification-pending {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	gap: 0.75rem;
	max-width: 460px;
	margin: 0 auto;
	text-align: center;
}

.title {
	font-size: 1.5rem;
	font-weight: 700;
	color: var(--ql-text);
	margin: 0;
}

.title-success {
	color: var(--ql-success);
}

.subtitle {
	font-size: 0.9375rem;
	color: var(--ql-text-muted);
	line-height: 1.5;
	margin: 0 0 0.75rem;
}

.subtitle strong {
	color: var(--ql-text);
	word-break: break-all;
}

.hint-card {
	width: 100%;
	padding: 0.875rem 1rem;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.625rem;
}

.hint {
	margin: 0;
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
	line-height: 1.5;
}

.actions {
	display: flex;
	align-items: center;
	gap: 0.75rem;
	margin-top: 0.5rem;
}

.secondary-btn {
	display: inline-flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.625rem 1.25rem;
	font-size: 0.875rem;
	font-weight: 600;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	cursor: pointer;
	transition: background 0.15s ease, border-color 0.15s ease;
}

.secondary-btn:hover:not(:disabled) {
	background: var(--ql-subtle);
	border-color: var(--ql-accent);
}

.secondary-btn:disabled {
	opacity: 0.65;
	cursor: not-allowed;
}

.link-btn {
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
	background: none;
	border: none;
	cursor: pointer;
	text-decoration: underline;
	text-underline-offset: 2px;
}

.link-btn:hover {
	color: var(--ql-text);
}

.change-email {
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
	width: min(100%, 22rem);
	margin-top: 0.75rem;
}

.change-email input {
	padding: 0.625rem 0.75rem;
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	background: var(--ql-bg);
	color: var(--ql-text);
}

.resent-toast {
	margin: 0.25rem 0 0;
	font-size: 0.8125rem;
	color: var(--ql-success);
}

.spinner {
	width: 1rem;
	height: 1rem;
	animation: spin 0.8s linear infinite;
}

.big-spinner {
	width: 2.5rem;
	height: 2.5rem;
	margin-top: 1rem;
	border: 3px solid var(--ql-border);
	border-top-color: var(--ql-accent);
	border-radius: 50%;
	animation: spin 0.8s linear infinite;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

.success-icon {
	width: 3rem;
	height: 3rem;
	color: var(--ql-success);
	background: rgba(34, 197, 94, 0.1);
	border-radius: 50%;
	padding: 0.5rem;
}

.success-icon svg {
	width: 100%;
	height: 100%;
}

.error-card {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 1rem;
	padding: 1.5rem 2rem;
	background: rgba(239, 68, 68, 0.08);
	border: 1px solid rgba(239, 68, 68, 0.2);
	border-radius: 0.75rem;
	max-width: 400px;
}

.error-icon {
	width: 2.5rem;
	height: 2.5rem;
	color: var(--ql-danger);
}

.error-icon svg {
	width: 100%;
	height: 100%;
}

.error-text {
	margin: 0;
	font-size: 0.875rem;
	color: var(--ql-danger);
	line-height: 1.5;
	word-break: break-word;
}

.retry-btn {
	padding: 0.625rem 1.5rem;
	font-size: 0.875rem;
	font-weight: 600;
	color: white;
	background: var(--ql-danger);
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
}

.retry-btn:hover {
	background: var(--ql-danger);
}
</style>
