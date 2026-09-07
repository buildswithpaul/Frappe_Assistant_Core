<template>
	<div class="terms-gate" data-test="terms-gate">
		<FacoRobot size="lg" mood="attentive" show-arms show-shadow />

		<div class="gate-content">
			<h1 class="gate-title">Updated terms need accepting</h1>

			<!-- Admin: can accept on the tenant's behalf -->
			<template v-if="canAccept">
				<p class="gate-text">
					Chat and model access are paused until this site accepts the current
					Terms and Conditions.
				</p>
				<p v-if="requiredVersion" class="gate-meta">
					Version <strong>{{ requiredVersion }}</strong>
					<span v-if="acceptedVersion"> — this site is on {{ acceptedVersion }}</span>
				</p>

				<p v-if="error" class="gate-error" role="alert">{{ error }}</p>

				<button
					class="gate-btn"
					data-test="terms-gate-review"
					:disabled="isAccepting"
					@click="openTerms"
				>
					{{ isAccepting ? "Accepting…" : "Review & accept terms" }}
				</button>
				<p class="gate-hint">Accepting applies to everyone on this site.</p>
			</template>

			<!-- Everyone else: acceptance binds the tenant, so it's not theirs to give -->
			<template v-else>
				<p class="gate-text" data-test="terms-gate-notice">
					Chat is paused until your administrator accepts the updated Terms and
					Conditions for this site.
				</p>
				<p class="gate-hint">
					Ask a <strong>System Manager</strong> to open FAC and accept them.
				</p>
			</template>
		</div>

		<TermsModal
			:is-open="modalOpen"
			:terms="terms"
			:is-loading="isLoadingTerms"
			:error="termsError"
			:is-registering="isAccepting"
			@close="modalOpen = false"
			@accept="handleAccept"
		/>
	</div>
</template>

<script setup>
import { computed, ref } from "vue";
import { storeToRefs } from "pinia";
import FacoRobot from "@/components/common/FacoRobot.vue";
import TermsModal from "@/components/onboarding/TermsModal.vue";
import { useUserStore } from "@/stores/userStore";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";

const userStore = useUserStore();
const { termsState } = storeToRefs(userStore);

const canAccept = computed(() => termsState.value?.can_accept === true);
const requiredVersion = computed(() => termsState.value?.required_version || null);
const acceptedVersion = computed(() => termsState.value?.accepted_version || null);

const modalOpen = ref(false);
const terms = ref(null);
const isLoadingTerms = ref(false);
const termsError = ref(null);
const isAccepting = ref(false);
const error = ref(null);

async function openTerms() {
	modalOpen.value = true;
	error.value = null;
	termsError.value = null;
	isLoadingTerms.value = true;
	try {
		const result = await api.registration.getTerms();
		if (result?.error) {
			termsError.value = result.error;
		} else if (result?.version) {
			terms.value = result;
		} else {
			termsError.value = "No terms available. Please try again later.";
		}
	} catch (err) {
		logger.error("Failed to load terms", err);
		termsError.value = "Couldn't load the terms. Please try again.";
	} finally {
		isLoadingTerms.value = false;
	}
}

/**
 * `version` comes from the terms we just displayed, not from the gate's
 * required_version — accepting must record what the admin actually read. AR
 * re-validates it against the active version and rejects a stale one.
 */
async function handleAccept(version) {
	isAccepting.value = true;
	error.value = null;
	try {
		const result = await api.registration.acceptUpdatedTerms(version);
		if (result?.success) {
			modalOpen.value = false;
			userStore.clearTermsGate();
		} else {
			error.value = result?.error || "Couldn't record your acceptance. Please try again.";
			modalOpen.value = false;
		}
	} catch (err) {
		logger.error("Terms acceptance failed", err);
		error.value = "Couldn't record your acceptance. Please try again.";
		modalOpen.value = false;
	} finally {
		isAccepting.value = false;
	}
}
</script>

<style scoped>
.terms-gate {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	min-height: 100%;
	padding: 2rem;
	gap: 1.5rem;
}

.gate-content {
	display: flex;
	flex-direction: column;
	align-items: center;
	text-align: center;
	max-width: 440px;
	gap: 0.75rem;
}

.gate-title {
	font-size: 1.5rem;
	font-weight: 700;
	color: var(--ql-text);
	margin: 0;
}

.gate-text {
	font-size: 0.9375rem;
	color: var(--ql-text-muted);
	line-height: 1.6;
	margin: 0;
}

.gate-meta {
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
	margin: 0;
}

.gate-error {
	font-size: 0.875rem;
	color: var(--ql-danger, #dc2626);
	margin: 0;
}

.gate-btn {
	margin-top: 0.5rem;
	padding: 0.625rem 1.25rem;
	font-size: 0.9375rem;
	font-weight: 600;
	color: var(--ql-on-accent, #fff);
	background: var(--ql-accent);
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: opacity 0.15s ease;
}

.gate-btn:hover:not(:disabled) {
	opacity: 0.9;
}

.gate-btn:disabled {
	opacity: 0.6;
	cursor: not-allowed;
}

.gate-hint {
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
	margin: 0;
}
</style>
