<template>
	<div class="onboarding-container">
		<!-- Email-verification waiting screen — AR sent a link to ownerEmail -->
		<template v-if="verificationPending">
			<EmailVerificationPending
				mode="awaiting-click"
				:owner-email="pendingEmail"
				:notice="pendingNotice"
				@resend="resend"
				@change-email="changeEmail"
			/>
		</template>

		<RegistrationOutcome
			v-else-if="registrationSuccess || waitlisted"
			:kind="registrationSuccess ? 'success' : 'waitlist'"
			:waitlist-position="waitlistPosition"
			:owner-email="ownerEmail"
		/>

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
					<ReconnectCard
						v-if="reregistration"
						:owner-email-masked="ownerEmailMasked"
						:sending="reconnecting"
						@send="handleReconnect"
					/>

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
import { ref, onMounted } from "vue";
import { api } from "@/api/client";
import {
	connectionErrorMessage as getErrorMessage,
	requestReconnectLink,
	useVerificationResume,
} from "@/composables/useVerificationResume";
import TermsModal from "./TermsModal.vue";
import PartnerCodeStep from "./PartnerCodeStep.vue";
import EmailVerificationPending from "./EmailVerificationPending.vue";
import SiteUnreachablePanel from "./SiteUnreachablePanel.vue";
import ReconnectCard from "./ReconnectCard.vue";
import RegistrationOutcome from "./RegistrationOutcome.vue";
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
// The registering admin's own address, resolved server-side. Prefills the
// owner field so the mailbox and the owner identity converge on purpose in
// the ordinary case, rather than by luck.
const suggestedEmail = ref("");
const reconnecting = ref(false);

const { verificationPending, pendingEmail, pendingNotice, enterPending, resume, resend, changeEmail } =
	useVerificationResume({ onVerified: () => emit("registered") });

onMounted(async () => {
	if (!props.isAdmin) return;
	try {
		const state = await api.registration.getState();
		suggestedEmail.value = state?.suggested_owner_email || "";
		ownerEmailMasked.value = state?.owner_email_masked || "";
		if (!resume(state) && state?.exists && state?.reregistration) {
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
		const result = await requestReconnectLink(ownerEmail.value || null);

		if (result?.success && result?.verification_pending) {
			reregistration.value = false;
			enterPending({ email: ownerEmailMasked.value, reconnect: true });
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
			enterPending({ email: ownerEmail.value });
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
