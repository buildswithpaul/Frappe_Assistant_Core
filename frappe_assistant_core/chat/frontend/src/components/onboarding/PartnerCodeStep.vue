<template>
	<div class="partner-card">
		<!-- Owner email — required for AR's email verification flow -->
		<div class="email-field">
			<label class="email-label" for="owner-email">Owner email</label>
			<input
				id="owner-email"
				v-model.trim="ownerEmail"
				type="email"
				class="email-input"
				:class="{ 'is-error': emailError }"
				placeholder="you@example.com"
				autocomplete="email"
				spellcheck="false"
				required
				:disabled="submitting"
				@blur="touchEmail"
			/>
			<p v-if="emailError" class="email-hint email-hint-error" role="alert">
				{{ emailError }}
			</p>
			<p v-else class="email-hint email-hint-muted">
				We'll send a verification link here to finish setup.
			</p>
		</div>

		<!-- Collapsed: subtle prompt link, only shown when user hasn't opened the input -->
		<button
			v-if="!expanded && !validatedPartner"
			type="button"
			class="partner-collapsed-link"
			@click="expand"
		>
			Have a partner code?
		</button>

		<!-- Expanded: input + validation feedback -->
		<div v-else class="partner-expanded">
			<div class="partner-card-header">
				<span class="partner-card-label">Partner code</span>
				<button
					v-if="!validatedPartner"
					type="button"
					class="partner-skip-link"
					@click="skip"
				>
					Skip
				</button>
			</div>

			<div
				class="partner-input-wrap"
				:class="{
					'is-valid': validatedPartner,
					'is-error': !!error,
				}"
			>
				<input
					ref="codeInput"
					v-model="code"
					type="text"
					class="partner-input"
					placeholder="e.g. testpartner"
					aria-label="Partner referral code"
					autocomplete="off"
					spellcheck="false"
					@input="onCodeInput"
					@blur="onBlurValidate"
					@keyup.enter="handlePrimaryClick"
					:disabled="validating || submitting"
				/>
				<span
					v-if="validating"
					class="partner-state-icon state-spinner"
					aria-hidden="true"
				></span>
				<svg
					v-else-if="validatedPartner"
					class="partner-state-icon state-check"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					aria-hidden="true"
				>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2.5"
						d="M5 13l4 4L19 7"
					/>
				</svg>
			</div>

			<p v-if="validatedPartner" class="partner-hint partner-hint-success">
				Referred by <strong>{{ validatedPartner.partner_name }}</strong>
			</p>
			<p v-else-if="error" class="partner-hint partner-hint-error" role="alert">
				{{ error }}
			</p>
			<p v-else class="partner-hint partner-hint-muted">
				Optional. This cannot be changed later.
			</p>
		</div>

		<!-- Primary CTA — single button, handles validate-then-continue -->
		<button
			type="button"
			class="partner-primary-btn"
			@click="handlePrimaryClick"
			:disabled="!canSubmit"
		>
			<svg
				v-if="submitting || validating"
				class="primary-spinner"
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
			<span v-else>{{ buttonLabel }}</span>
		</button>

		<p class="partner-legal-hint">You'll review our Terms before your account is created.</p>
	</div>
</template>

<script setup>
import { ref, computed, nextTick } from "vue";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";

const props = defineProps({
	submitting: {
		type: Boolean,
		default: false,
	},
});

const emit = defineEmits(["submit"]);

const expanded = ref(false);
const code = ref("");
const validating = ref(false);
const error = ref(null);
const validatedPartner = ref(null);
const codeInput = ref(null);
// If the user clicks the primary button while a blur-validate is in flight,
// remember the intent and fire it automatically when validation resolves.
const pendingSubmit = ref(false);

const ownerEmail = ref("");
const emailTouched = ref(false);

// HTML5-grade email validation — we only need to catch obvious typos before
// hitting the backend. Frappe's validate_email_address is authoritative.
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const isEmailValid = computed(() => EMAIL_RE.test(ownerEmail.value));
const emailError = computed(() => {
	if (!emailTouched.value) return null;
	if (!ownerEmail.value) return "Owner email is required.";
	if (!isEmailValid.value) return "Please enter a valid email address.";
	return null;
});

function touchEmail() {
	emailTouched.value = true;
}

const trimmed = computed(() => code.value.trim().toLowerCase());
const hasCodeEntered = computed(() => trimmed.value.length > 0);
const isValidatedForCurrent = computed(
	() => !!validatedPartner.value && validatedPartner.value.referral_code === trimmed.value
);

// Button copy reflects the next concrete action the click will take.
const buttonLabel = computed(() => {
	if (!hasCodeEntered.value) return "Get Started";
	if (isValidatedForCurrent.value) return "Continue";
	return "Validate & Continue";
});

// Button state:
// - Disabled while parent is registering (prevents double-submit).
// - Disabled until owner email is present and well-formed — email is the
//   only mandatory field on this card.
// - STAYS ENABLED during in-flight blur-validation so the click is captured
//   and queued via `pendingSubmit`.
const canSubmit = computed(() => !props.submitting && isEmailValid.value);

// Payload emitted to parent on submit. Parent decides what to do with the
// partner side; email is always passed alongside.
//   partner: null           → proceed without a partner
//   partner: string (code)  → validated code
//   partner: { unvalidated: code } → parent must validate+register
const payload = computed(() => {
	let partner;
	if (!hasCodeEntered.value) partner = null;
	else if (isValidatedForCurrent.value) partner = trimmed.value;
	else partner = { unvalidated: trimmed.value };
	return { ownerEmail: ownerEmail.value, partner };
});

function handlePrimaryClick() {
	if (props.submitting) return;
	// Force email validation feedback if the user clicks without ever blurring.
	emailTouched.value = true;
	if (!isEmailValid.value) return;
	// Queue the click if a blur-validate is already running. When runValidate's
	// finally sees pendingSubmit=true and validation succeeded, it will emit on
	// the user's behalf.
	if (validating.value) {
		pendingSubmit.value = true;
		return;
	}
	emit("submit", payload.value);
}

async function expand() {
	expanded.value = true;
	await nextTick();
	codeInput.value?.focus();
}

function skip() {
	code.value = "";
	validatedPartner.value = null;
	error.value = null;
	expanded.value = false;
}

function onCodeInput() {
	code.value = code.value.toLowerCase();
	// Any edit invalidates prior success — user must re-validate (implicitly on blur).
	if (validatedPartner.value) validatedPartner.value = null;
	if (error.value) error.value = null;
}

async function onBlurValidate() {
	// Silently validate when the user leaves the field, so they see confirmation
	// before clicking the primary button. Empty field is fine — do nothing.
	if (!hasCodeEntered.value) return;
	if (isValidatedForCurrent.value) return;
	await runValidate({ silent: true });
}

async function runValidate({ silent = false } = {}) {
	if (!hasCodeEntered.value) {
		if (!silent) error.value = "Please enter a partner code";
		return { ok: false };
	}
	validating.value = true;
	error.value = null;
	try {
		const result = await api.registration.validatePartnerCode(trimmed.value);
		if (result?.valid) {
			validatedPartner.value = {
				partner_name: result.partner_name,
				referral_code: result.referral_code,
			};
			// Snap to canonical server-side casing so the computed comparison matches.
			code.value = result.referral_code;
			return { ok: true, code: result.referral_code };
		}
		error.value = result?.error || "Invalid or inactive referral code";
		return { ok: false };
	} catch (err) {
		// The API helper may throw `API Error: 4xx - <html>` when the backend raises.
		// Never surface raw HTML or stack traces — keep the card copy clean.
		logger.error("Partner code validation failed", err);
		error.value = "Couldn't check that code right now. Please try again.";
		return { ok: false };
	} finally {
		validating.value = false;
		// Resolve any queued click: if the user clicked the primary button while
		// this validation was running, fire the submit now — but only if the
		// code is actually valid. On invalid, drop the queued click and let the
		// inline error message guide them.
		if (pendingSubmit.value) {
			pendingSubmit.value = false;
			if (validatedPartner.value) {
				emit("submit", { ownerEmail: ownerEmail.value, partner: trimmed.value });
			}
		}
	}
}

// Parent can call this to kick validation from the outside if it receives an
// { unvalidated: code } payload — but we also expose the pure result so the
// parent doesn't need to re-call the API.
defineExpose({ runValidate });
</script>

<style scoped>
.partner-card {
	display: flex;
	flex-direction: column;
	align-items: stretch;
	gap: 0.75rem;
	width: 100%;
	max-width: 380px;
	padding: 1.25rem;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.875rem;
	box-shadow: 0 4px 20px -8px rgba(0, 0, 0, 0.2);
}

.email-field {
	display: flex;
	flex-direction: column;
	gap: 0.375rem;
	text-align: left;
}

.email-label {
	font-size: 0.75rem;
	font-weight: 600;
	text-transform: uppercase;
	letter-spacing: 0.05em;
	color: var(--ql-text-muted);
}

.email-input {
	padding: 0.625rem 0.75rem;
	font-size: 0.875rem;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	outline: none;
	transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.email-input:focus {
	border-color: var(--ql-accent);
	box-shadow: 0 0 0 3px var(--ql-accent-soft);
}

.email-input:disabled {
	opacity: 0.6;
}

.email-input.is-error {
	border-color: var(--ql-danger);
}

.email-hint {
	margin: 0;
	font-size: 0.75rem;
	line-height: 1.4;
}

.email-hint-muted {
	color: var(--ql-text-muted);
}

.email-hint-error {
	color: var(--ql-danger);
}

.partner-collapsed-link {
	align-self: center;
	padding: 0.25rem 0.5rem;
	font-size: 0.8125rem;
	color: var(--ql-accent);
	background: none;
	border: none;
	cursor: pointer;
	text-decoration: underline;
	text-underline-offset: 3px;
}

.partner-collapsed-link:hover {
	opacity: 0.85;
}

.partner-expanded {
	display: flex;
	flex-direction: column;
	gap: 0.375rem;
}

.partner-card-header {
	display: flex;
	justify-content: space-between;
	align-items: center;
}

.partner-card-label {
	font-size: 0.75rem;
	font-weight: 600;
	text-transform: uppercase;
	letter-spacing: 0.05em;
	color: var(--ql-text-muted);
}

.partner-skip-link {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	background: none;
	border: none;
	cursor: pointer;
	padding: 0;
	text-decoration: underline;
	text-underline-offset: 2px;
}

.partner-skip-link:hover {
	color: var(--ql-text);
}

.partner-input-wrap {
	position: relative;
	display: flex;
	align-items: center;
}

.partner-input {
	flex: 1;
	padding: 0.625rem 2.25rem 0.625rem 0.75rem;
	font-size: 0.875rem;
	font-family: monospace;
	letter-spacing: 0.04em;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	outline: none;
	transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.partner-input:focus {
	border-color: var(--ql-accent);
	box-shadow: 0 0 0 3px var(--ql-accent-soft);
}

.partner-input:disabled {
	opacity: 0.6;
}

.partner-input-wrap.is-valid .partner-input {
	border-color: var(--ql-success);
}

.partner-input-wrap.is-error .partner-input {
	border-color: var(--ql-danger);
}

.partner-state-icon {
	position: absolute;
	right: 0.625rem;
	width: 1.125rem;
	height: 1.125rem;
	display: flex;
	align-items: center;
	justify-content: center;
}

.partner-state-icon.state-check {
	color: var(--ql-success);
}

.partner-state-icon.state-spinner {
	width: 0.875rem;
	height: 0.875rem;
	border: 2px solid var(--ql-border);
	border-top-color: var(--ql-accent);
	border-radius: 50%;
	animation: partner-spin 0.8s linear infinite;
}

@keyframes partner-spin {
	to {
		transform: rotate(360deg);
	}
}

.partner-hint {
	margin: 0;
	font-size: 0.75rem;
	line-height: 1.4;
}

.partner-hint-muted {
	color: var(--ql-text-muted);
}

.partner-hint-success {
	color: var(--ql-success);
}

.partner-hint-success strong {
	color: var(--ql-text);
}

.partner-hint-error {
	color: var(--ql-danger);
}

.partner-primary-btn {
	display: flex;
	align-items: center;
	justify-content: center;
	gap: 0.5rem;
	padding: 0.75rem 1.5rem;
	margin-top: 0.25rem;
	font-size: 0.9375rem;
	font-weight: 600;
	color: white;
	background: linear-gradient(
		135deg,
		var(--ql-accent) 0%,
		var(--ql-accent-hover) 100%
	);
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: transform 0.15s ease, box-shadow 0.15s ease, opacity 0.15s ease;
}

.partner-primary-btn:hover:not(:disabled) {
	transform: translateY(-1px);
	box-shadow: 0 4px 12px var(--ql-accent-soft);
}

.partner-primary-btn:disabled {
	opacity: 0.65;
	cursor: not-allowed;
}

.primary-spinner {
	width: 1.125rem;
	height: 1.125rem;
	animation: partner-spin 1s linear infinite;
}

.partner-legal-hint {
	margin: 0;
	font-size: 0.6875rem;
	text-align: center;
	color: var(--ql-text-muted);
}
</style>
