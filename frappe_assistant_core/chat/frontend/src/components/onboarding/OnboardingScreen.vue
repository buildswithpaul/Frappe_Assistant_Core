<template>
	<div class="onboarding-container">
		<!-- Email-verification waiting screen — AR sent a link to ownerEmail -->
		<template v-if="verificationPending">
			<EmailVerificationPending
				mode="awaiting-click"
				:owner-email="ownerEmail || ownerEmailMasked"
				:notice="pendingNotice"
				@resend="handleResend"
				@change-email="handleChangeEmail"
			/>
		</template>

		<!-- Success State - shown briefly after registration -->
		<template v-else-if="registrationSuccess">
			<div class="success-state">
				<FacoRobot
					size="lg"
					mood="excited"
					show-arms
					show-shadow
					extra-class="robot-celebrate"
				/>

				<div class="success-content">
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
					<h1 class="success-title">Connected!</h1>
					<p class="success-message">FACO is ready to help you.</p>
				</div>
			</div>
		</template>

		<!-- Waitlist State — registration is at capacity; applicant is queued -->
		<template v-else-if="waitlisted">
			<div class="waitlist-state" data-test="waitlist-state">
				<FacoRobot size="lg" mood="attentive" show-arms show-shadow />
				<div class="waitlist-content">
					<h1 class="waitlist-title">You're on the waitlist</h1>
					<p v-if="waitlistPosition" class="waitlist-position">
						Position <strong>#{{ waitlistPosition }}</strong> in the queue
					</p>
					<p class="waitlist-message">
						Registration is at capacity right now. We'll email
						<strong>{{ ownerEmail }}</strong> the moment a slot opens — just
						click the link in that email to finish setting up.
					</p>
				</div>
			</div>
		</template>

		<!-- Normal Onboarding Flow -->
		<template v-else>
			<!-- Robot Avatar — reflects registration state -->
			<FacoRobot
				size="lg"
				float
				show-arms
				show-shadow
				:mood="isRegistering ? 'thinking' : error ? 'concerned' : 'attentive'"
				extra-class="mb-6"
			/>

			<!-- Welcome Title -->
			<h1 class="onboarding-title">Welcome to FACO Assistant</h1>
			<p class="onboarding-subtitle">Your intelligent AI copilot for Frappe and ERPNext</p>

			<!-- Admin View: Registration -->
			<template v-if="props.isAdmin">
				<!-- Registration Section -->
				<div class="registration-section">
					<!-- Reconnect: returning tenant detected on boot -->
					<div v-if="reregistration" class="reconnect-card" data-test="reconnect-card">
						<h2 class="reconnect-title">Reconnect this site</h2>
						<p class="reconnect-text">
							We'll email a verification link to
							<strong>{{ ownerEmailMasked }}</strong>. Click it to finish reconnecting.
						</p>
						<button
							class="reconnect-btn"
							data-test="reconnect-send"
							:disabled="reconnecting"
							@click="handleReconnect"
						>
							<span v-if="!reconnecting">Send verification email</span>
							<span v-else>Sending…</span>
						</button>
					</div>

					<!-- Default: error state, or inline card with optional partner code + primary CTA -->
					<template v-else>
						<!-- Unreachable site: retrying can never help, so route to the
						     two doors (local MCP server, or expose the site) instead. -->
						<SiteUnreachablePanel
							v-if="errorCode === 'SITE_UNREACHABLE'"
							:message="error"
							:retrying="isRegistering || reconnecting"
							@retry="resetError"
						/>

						<!-- Error State with Retry -->
						<div v-else-if="error" class="error-card">
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
							<p class="error-text">{{ error }}</p>
							<div class="error-actions">
								<button
									class="retry-btn"
									@click="resetError"
									:disabled="isRegistering"
								>
									<svg
										v-if="isRegistering"
										class="spinner-small"
										viewBox="0 0 24 24"
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
									<span v-else>Try Again</span>
								</button>
							</div>
						</div>

						<!-- Default: inline card with optional partner code + primary CTA -->
						<PartnerCodeStep
							v-else
							ref="partnerCard"
							:submitting="isRegistering"
							:initial-email="suggestedEmail"
							@submit="handleSubmit"
						/>
					</template>
				</div>
			</template>

			<!-- Non-Admin View: Contact Admin Message -->
			<template v-else>
				<div class="contact-admin-card">
					<div class="info-icon">
						<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
							/>
						</svg>
					</div>
					<h2>Setup Required</h2>
					<p class="primary-text">
						FACO needs to be connected to a FAC Cloud server before you can
						use it.
					</p>
					<p class="secondary-text">
						Please contact your system administrator to complete the setup.
					</p>
				</div>
			</template>
		</template>

		<!-- Terms Modal -->
		<TermsModal
			:is-open="showTermsModal"
			:terms="termsContent"
			:is-loading="termsLoading"
			:error="termsError"
			:is-registering="isRegistering"
			@close="handleTermsClose"
			@accept="handleTermsAccepted"
		/>
	</div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from "vue";
import { api } from "@/api/client";
import TermsModal from "./TermsModal.vue";
import PartnerCodeStep from "./PartnerCodeStep.vue";
import EmailVerificationPending from "./EmailVerificationPending.vue";
import SiteUnreachablePanel from "./SiteUnreachablePanel.vue";
import FacoRobot from "@/components/common/FacoRobot.vue";

const props = defineProps({
	isAdmin: {
		type: Boolean,
		default: false,
	},
});

const emit = defineEmits(["registered"]);

const isRegistering = ref(false);
const registrationSuccess = ref(false);
const verificationPending = ref(false);
const waitlisted = ref(false);
const waitlistPosition = ref(null);
// Waitlist promotion deep link (?action=resume_registration&promotion_token=...)
// was captured + stripped in index.html; read once so a refresh doesn't replay.
const promotionToken = ref(window.__facoPromotionToken || null);
if (window.__facoPromotionToken) {
	delete window.__facoPromotionToken;
}
const error = ref(null);
// AR's structured error_code, when it sends one. Drives which failure UI the
// screen shows — SITE_UNREACHABLE gets the two-door panel, everything else
// falls back to the generic retry card.
const errorCode = ref(null);

// Owner email + partner code captured from the onboarding card.
// Both are persisted across the terms modal so the registration call
// can reference them after the user accepts.
const ownerEmail = ref("");
const referralCode = ref(null);
const partnerCard = ref(null);

// Terms Modal state
const showTermsModal = ref(false);
const termsContent = ref(null);
const termsLoading = ref(false);
const termsError = ref(null);

// Reconnect flow — returning tenant detected on boot
const reregistration = ref(false);
const ownerEmailMasked = ref("");
const pendingNotice = ref("");
// The registering admin's own address, resolved server-side. Prefills the
// owner field so the mailbox and the owner identity converge on purpose in
// the ordinary case, rather than by luck.
const suggestedEmail = ref("");
const reconnecting = ref(false);

onMounted(async () => {
	if (!props.isAdmin) return;
	try {
		const state = await api.registration.getState();
		suggestedEmail.value = state?.suggested_owner_email || "";
		ownerEmailMasked.value = state?.owner_email_masked || "";
		if (state?.status === "Pending Email Verification") {
			verificationPending.value = true;
		} else if (state?.exists && state?.reregistration) {
			reregistration.value = true;
		}
	} catch (_) {
		// Lookup failed — fall through to the normal first-run funnel.
	}
});

async function handleReconnect() {
	reconnecting.value = true;
	error.value = null;
	errorCode.value = null;
	try {
		const terms = await api.registration.getTerms();
		if (!terms?.version) throw new Error("No terms available");
		const result = await api.registration.register(ownerEmail.value || null, terms.version);

		if (result?.success && result?.verification_pending) {
			reregistration.value = false;
			verificationPending.value = true;
		} else if (result?.success) {
			registrationSuccess.value = true;
			setTimeout(() => emit("registered"), 1500);
		} else {
			error.value = result?.error || "Reconnect failed. Please try again.";
			errorCode.value = result?.error_code || null;
			reregistration.value = false;
		}
	} catch (err) {
		error.value = getErrorMessage(err);
		reregistration.value = false;
	} finally {
		reconnecting.value = false;
	}
}

function resetError() {
	error.value = null;
	errorCode.value = null;
}

// Called by PartnerCodeStep's primary button. Payload shape:
//   { ownerEmail: string, partner: null | string | { unvalidated: string } }
async function handleSubmit(payload) {
	if (!payload || !payload.ownerEmail) return; // card guards this, defensive
	ownerEmail.value = payload.ownerEmail;
	const partner = payload.partner;

	if (partner && typeof partner === "object" && "unvalidated" in partner) {
		const result = await partnerCard.value?.runValidate();
		if (!result?.ok) {
			// Card shows the error inline; nothing else to do.
			return;
		}
		referralCode.value = result.code;
	} else {
		referralCode.value = typeof partner === "string" ? partner : null;
	}

	openTermsFlow();
}

async function openTermsFlow() {
	termsLoading.value = true;
	termsError.value = null;
	showTermsModal.value = true;

	try {
		const terms = await api.registration.getTerms();

		if (terms?.error) {
			termsError.value = terms.error;
		} else if (terms?.version) {
			termsContent.value = terms;
		} else {
			termsError.value = "No terms available. Please try again later.";
		}
	} catch (err) {
		termsError.value = getErrorMessage(err);
	} finally {
		termsLoading.value = false;
	}
}

function handleTermsClose() {
	showTermsModal.value = false;
	termsContent.value = null;
	termsError.value = null;
}

async function handleTermsAccepted(termsVersion) {
	isRegistering.value = true;
	error.value = null;
	errorCode.value = null;

	try {
		const result = await api.registration.register(
			ownerEmail.value,
			termsVersion,
			referralCode.value,
			promotionToken.value
		);

		if (result?.success && result?.verification_pending) {
			// AR queued a verification email — show the pending screen until the
			// admin clicks the link (which lands back here via the deep-link
			// handler in App.vue → EmailVerificationPending in mode="verifying").
			showTermsModal.value = false;
			verificationPending.value = true;
		} else if (result?.success && result?.waitlisted) {
			showTermsModal.value = false;
			waitlisted.value = true;
			waitlistPosition.value = result?.waitlist_position ?? null;
		} else if (result?.success) {
			// Legacy / re-registration path — secret returned immediately.
			showTermsModal.value = false;
			registrationSuccess.value = true;
			setTimeout(() => {
				emit("registered");
			}, 1500);
		} else {
			showTermsModal.value = false;
			error.value = result?.error || "Registration failed. Please try again.";
			errorCode.value = result?.error_code || null;
		}
	} catch (err) {
		showTermsModal.value = false;
		error.value = getErrorMessage(err);
	} finally {
		isRegistering.value = false;
	}
}

// Resend goes to the address AR already stored. It does not re-accept terms
// and it does not clear a secret that another tab has already saved.
async function handleResend(done) {
	pendingNotice.value = "";
	try {
		const result = await api.registration.resendVerification();
		if (result?.already_verified) {
			emit("registered");
			return;
		}
		if (result?.retry_after && !result?.success) {
			pendingNotice.value = `Wait ${result.retry_after}s before sending again.`;
		} else if (result?.success) {
			pendingNotice.value = "Email resent. Check your inbox.";
			if (result.owner_email_masked) ownerEmailMasked.value = result.owner_email_masked;
		} else {
			pendingNotice.value = result?.error || "Could not resend the email.";
		}
	} catch (err) {
		pendingNotice.value = getErrorMessage(err);
	} finally {
		if (typeof done === "function") done();
	}
}

// Correct the address in place. Leaving the screen used to send the link to
// the old address while saying it went to the new one.
async function handleChangeEmail(address, done) {
	pendingNotice.value = "";
	try {
		const result = await api.registration.changePendingEmail(address);
		if (result?.success) {
			ownerEmail.value = "";
			ownerEmailMasked.value = result.owner_email_masked || address;
			pendingNotice.value = "Verification email sent to the new address.";
		} else {
			pendingNotice.value = result?.error || "Could not change the email.";
		}
	} catch (err) {
		pendingNotice.value = getErrorMessage(err);
	} finally {
		if (typeof done === "function") done();
	}
}

let pendingPoll = null;

async function checkVerificationLanded() {
	if (!verificationPending.value || document.hidden) return;
	try {
		const state = await api.registration.getState();
		if (state?.local_status === "Registered") emit("registered");
	} catch (_) {
		// A failed poll just waits for the next one.
	}
}

function stopPendingPoll() {
	if (pendingPoll) clearInterval(pendingPoll);
	pendingPoll = null;
	document.removeEventListener("visibilitychange", checkVerificationLanded);
}

watch(verificationPending, (pending) => {
	stopPendingPoll();
	if (!pending) return;
	pendingPoll = setInterval(checkVerificationLanded, 5000);
	document.addEventListener("visibilitychange", checkVerificationLanded);
});

onBeforeUnmount(stopPendingPoll);

function getErrorMessage(err) {
	const message = err.message || "";

	if (message.includes("Failed to fetch") || message.includes("NetworkError")) {
		return "Cannot connect to the server. Please check your internet connection.";
	}
	if (message.includes("timeout") || message.includes("Timeout")) {
		return "Connection timed out. The server may be temporarily unavailable.";
	}
	if (message.includes("500") || message.includes("Internal")) {
		return "The server encountered an error. Please try again in a few moments.";
	}
	if (message.includes("401") || message.includes("403")) {
		return "Authentication failed. Please refresh and try again.";
	}

	return message || "Failed to connect to the server. Please try again.";
}
</script>

<style scoped>
.onboarding-container {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	min-height: 100%;
	padding: 2rem;
	text-align: center;
}

.onboarding-title {
	font-family: var(--ql-font-serif);
	font-size: 1.75rem;
	font-weight: 700;
	color: var(--ql-text);
	margin-bottom: 0.5rem;
}

.onboarding-subtitle {
	font-size: 1rem;
	color: var(--ql-text-muted);
	margin-bottom: 2rem;
	max-width: 400px;
}

/* Registration Section */
.registration-section {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 0.75rem;
}

.spinner {
	width: 1.25rem;
	height: 1.25rem;
	animation: spin 1s linear infinite;
}

@keyframes spin {
	from {
		transform: rotate(0deg);
	}
	to {
		transform: rotate(360deg);
	}
}

/* Error Card - improved error display */
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

.error-card .error-icon {
	width: 2.5rem;
	height: 2.5rem;
	color: var(--ql-danger);
}

.error-card .error-icon svg {
	width: 100%;
	height: 100%;
}

.error-text {
	font-size: 0.875rem;
	color: var(--ql-danger);
	text-align: center;
	line-height: 1.5;
	word-break: break-word;
	overflow-wrap: anywhere;
	max-width: 100%;
}

.error-actions {
	display: flex;
	gap: 0.75rem;
}

.retry-btn {
	display: flex;
	align-items: center;
	justify-content: center;
	gap: 0.5rem;
	padding: 0.625rem 1.5rem;
	font-size: 0.875rem;
	font-weight: 600;
	color: white;
	background: var(--ql-danger);
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.2s ease;
	min-width: 120px;
}

.retry-btn:hover:not(:disabled) {
	background: var(--ql-danger);
	transform: translateY(-1px);
}

.retry-btn:disabled {
	opacity: 0.7;
	cursor: not-allowed;
}

.spinner-small {
	width: 1rem;
	height: 1rem;
	animation: spin 1s linear infinite;
}

/* Success State */
.success-state {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	min-height: 100%;
	animation: success-fade-in 0.5s ease;
}

.success-content {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 0.5rem;
	margin-top: 1.5rem;
}

.success-icon {
	width: 3rem;
	height: 3rem;
	color: var(--ql-success);
	background: rgba(34, 197, 94, 0.1);
	border-radius: 50%;
	padding: 0.5rem;
	animation: success-pop 0.5s ease 0.2s both;
}

.success-icon svg {
	width: 100%;
	height: 100%;
}

.success-title {
	font-family: var(--ql-font-serif);
	font-size: 1.75rem;
	font-weight: 700;
	color: var(--ql-success);
	animation: success-slide-up 0.5s ease 0.3s both;
}

.success-message {
	font-size: 1rem;
	color: var(--ql-text-muted);
	animation: success-slide-up 0.5s ease 0.4s both;
}

.waitlist-state {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	min-height: 100%;
	animation: success-fade-in 0.5s ease;
}

.waitlist-content {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 0.5rem;
	margin-top: 1.5rem;
	max-width: 28rem;
	text-align: center;
}

.waitlist-title {
	font-family: var(--ql-font-serif);
	font-size: 1.75rem;
	font-weight: 700;
	color: var(--ql-text);
}

.waitlist-position {
	font-size: 1rem;
	color: var(--ql-accent);
}

.waitlist-message {
	font-size: 0.9375rem;
	color: var(--ql-text-muted);
	line-height: 1.5;
}

/* Robot celebrate animation — preserves the .faco-robot-lg base scale(1.2).
   If we only wrote scale(1) here, the keyframe would override the base
   transform and the robot would shrink mid-animation, snapping back at the
   end. Multiplying through 1.2 keeps the size coherent. */
.robot-celebrate {
	animation: robot-celebrate 1s ease-in-out;
}

@keyframes robot-celebrate {
	0%,
	100% {
		transform: scale(1.2) rotate(0deg);
	}
	25% {
		transform: scale(1.32) rotate(-5deg);
	}
	50% {
		transform: scale(1.38) rotate(5deg);
	}
	75% {
		transform: scale(1.32) rotate(-3deg);
	}
}

@keyframes success-fade-in {
	from {
		opacity: 0;
	}
	to {
		opacity: 1;
	}
}

@keyframes success-pop {
	from {
		transform: scale(0);
		opacity: 0;
	}
	to {
		transform: scale(1);
		opacity: 1;
	}
}

@keyframes success-slide-up {
	from {
		transform: translateY(20px);
		opacity: 0;
	}
	to {
		transform: translateY(0);
		opacity: 1;
	}
}

/* Reconnect Card */
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

/* Contact Admin Card */
.contact-admin-card {
	max-width: 400px;
	padding: 2rem;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
}

.info-icon {
	width: 3rem;
	height: 3rem;
	margin: 0 auto 1rem;
	color: var(--ql-accent);
}

.info-icon svg {
	width: 100%;
	height: 100%;
}

.contact-admin-card h2 {
	font-size: 1.25rem;
	font-weight: 600;
	color: var(--ql-text);
	margin-bottom: 0.75rem;
}

.contact-admin-card .primary-text {
	font-size: 0.875rem;
	color: var(--ql-text);
	margin-bottom: 0.5rem;
}

.contact-admin-card .secondary-text {
	font-size: 0.875rem;
	color: var(--ql-text-muted);
}

/* Responsive */
@media (max-width: 640px) {
	.onboarding-container {
		padding: 1.5rem;
	}

	.onboarding-title {
		font-size: 1.5rem;
	}
}
</style>
