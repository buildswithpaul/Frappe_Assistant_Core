<template>
	<Teleport to="body">
		<div v-if="isOpen" class="modal-overlay" @click.self="$emit('close')">
			<div class="terms-modal-container">
				<!-- Header -->
				<div class="modal-header">
					<h2 class="modal-title">Terms and Conditions</h2>
					<button @click="$emit('close')" class="close-btn" aria-label="Close">
						<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M6 18L18 6M6 6l12 12"
							/>
						</svg>
					</button>
				</div>

				<!-- Content -->
				<div class="modal-body">
					<!-- Loading State -->
					<div v-if="isLoading" class="loading-state">
						<div class="spinner"></div>
						<span>Loading terms...</span>
					</div>

					<!-- Error State -->
					<div v-else-if="error" class="error-state">
						<svg
							class="error-icon"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
							/>
						</svg>
						<p class="error-title">Failed to load terms</p>
						<p class="error-description">{{ error }}</p>
						<button @click="$emit('close')" class="retry-btn">Close</button>
					</div>

					<!-- Terms Content -->
					<div v-else-if="terms" class="terms-content">
						<!-- Summary -->
						<div v-if="terms.summary" class="terms-summary">
							<p>{{ terms.summary }}</p>
						</div>

						<!-- Terms of Service Section -->
						<div class="terms-section">
							<div class="section-header" @click="toggleSection('tos')">
								<h3 class="section-title">Terms of Service</h3>
								<svg
									:class="['chevron', { rotated: expandedSections.tos }]"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
								>
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d="M19 9l-7 7-7-7"
									/>
								</svg>
							</div>
							<div
								v-show="expandedSections.tos"
								class="section-content"
								v-html="sanitizedTermsOfService"
							></div>
						</div>

						<!-- Privacy Policy Section -->
						<div class="terms-section">
							<div class="section-header" @click="toggleSection('privacy')">
								<h3 class="section-title">Privacy Policy</h3>
								<svg
									:class="['chevron', { rotated: expandedSections.privacy }]"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
								>
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d="M19 9l-7 7-7-7"
									/>
								</svg>
							</div>
							<div
								v-show="expandedSections.privacy"
								class="section-content"
								v-html="sanitizedPrivacyPolicy"
							></div>
						</div>

						<!-- Data Processing Agreement (if exists) -->
						<div v-if="terms.data_processing_agreement" class="terms-section">
							<div class="section-header" @click="toggleSection('dpa')">
								<h3 class="section-title">Data Processing Agreement</h3>
								<svg
									:class="['chevron', { rotated: expandedSections.dpa }]"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
								>
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d="M19 9l-7 7-7-7"
									/>
								</svg>
							</div>
							<div
								v-show="expandedSections.dpa"
								class="section-content"
								v-html="sanitizedDataProcessingAgreement"
							></div>
						</div>

						<!-- Version Info -->
						<div class="terms-meta">
							<span>Version {{ terms.version }}</span>
							<span v-if="terms.effective_date"
								>Effective: {{ formatDate(terms.effective_date) }}</span
							>
						</div>
					</div>
				</div>

				<!-- Footer -->
				<div v-if="terms && !error && !isLoading" class="modal-footer">
					<label class="checkbox-wrapper">
						<input type="checkbox" v-model="accepted" class="terms-checkbox" />
						<span class="checkbox-label">
							I have read and accept the Terms and Conditions
						</span>
					</label>
					<div class="footer-actions">
						<button @click="$emit('close')" class="cancel-btn">Cancel</button>
						<button
							@click="handleAccept"
							:disabled="!accepted || isRegistering"
							class="accept-btn"
						>
							<span v-if="isRegistering" class="btn-loading">
								<div class="spinner-small"></div>
								Registering...
							</span>
							<span v-else>Accept & Register</span>
						</button>
					</div>
				</div>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
import { ref, reactive, computed } from "vue";
import DOMPurify from "dompurify";
import { formatDateLong } from "@/composables/useFormatters";

const props = defineProps({
	isOpen: {
		type: Boolean,
		required: true,
	},
	terms: {
		type: Object,
		default: null,
	},
	isLoading: {
		type: Boolean,
		default: false,
	},
	error: {
		type: String,
		default: null,
	},
	isRegistering: {
		type: Boolean,
		default: false,
	},
});

const emit = defineEmits(["close", "accept"]);

const accepted = ref(false);
const expandedSections = reactive({
	tos: true,
	privacy: true,
	dpa: false,
});

// Terms HTML comes from the backend and is rendered via v-html. Even though
// the source is trusted, we sanitize through DOMPurify to defend against
// compromise or misconfiguration that might let attacker-controlled HTML
// reach this modal.
const sanitizedTermsOfService = computed(() =>
	props.terms?.terms_of_service ? DOMPurify.sanitize(props.terms.terms_of_service) : ""
);
const sanitizedPrivacyPolicy = computed(() =>
	props.terms?.privacy_policy ? DOMPurify.sanitize(props.terms.privacy_policy) : ""
);
const sanitizedDataProcessingAgreement = computed(() =>
	props.terms?.data_processing_agreement
		? DOMPurify.sanitize(props.terms.data_processing_agreement)
		: ""
);

function toggleSection(section) {
	expandedSections[section] = !expandedSections[section];
}

// formatDate → shared formatDateLong from useFormatters
const formatDate = formatDateLong;

function handleAccept() {
	if (accepted.value && props.terms?.version) {
		emit("accept", props.terms.version);
	}
}
</script>

<style scoped>
.modal-overlay {
	position: fixed;
	inset: 0;
	background-color: rgba(0, 0, 0, 0.5);
	display: flex;
	align-items: center;
	justify-content: center;
	z-index: 100;
	padding: 1rem;
}

.terms-modal-container {
	background: var(--ql-surface);
	border-radius: 1rem;
	width: 100%;
	max-width: 700px;
	max-height: 90vh;
	display: flex;
	flex-direction: column;
	box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
}

.modal-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 1.25rem 1.5rem;
	border-bottom: 1px solid var(--ql-border);
}

.modal-title {
	font-size: 1.25rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0;
}

.close-btn {
	padding: 0.5rem;
	color: var(--ql-text-muted);
	background: transparent;
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.close-btn:hover {
	background-color: var(--ql-subtle);
	color: var(--ql-text);
}

.modal-body {
	flex: 1;
	overflow-y: auto;
	padding: 1.5rem;
}

/* Loading State */
.loading-state {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 3rem 1rem;
	gap: 1rem;
	color: var(--ql-text-muted);
}

.spinner {
	width: 2rem;
	height: 2rem;
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

/* Error State */
.error-state {
	display: flex;
	flex-direction: column;
	align-items: center;
	padding: 2rem 1rem;
	text-align: center;
	gap: 0.75rem;
}

.error-icon {
	width: 3rem;
	height: 3rem;
	color: var(--ql-danger);
}

.error-title {
	font-weight: 600;
	color: var(--ql-text);
	margin: 0;
}

.error-description {
	color: var(--ql-text-muted);
	font-size: 0.875rem;
	margin: 0;
}

.retry-btn {
	margin-top: 0.5rem;
	padding: 0.5rem 1rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-accent);
	background: transparent;
	border: 1px solid var(--ql-accent);
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.retry-btn:hover {
	background: var(--ql-accent);
	color: white;
}

/* Terms Content */
.terms-content {
	display: flex;
	flex-direction: column;
	gap: 1rem;
}

.terms-summary {
	padding: 1rem;
	background-color: var(--ql-subtle);
	border-radius: 0.5rem;
	color: var(--ql-text);
	font-size: 0.9375rem;
	line-height: 1.6;
}

.terms-section {
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	overflow: hidden;
}

.section-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 1rem;
	background-color: var(--ql-subtle);
	cursor: pointer;
	transition: background-color 0.15s ease;
}

.section-header:hover {
	background-color: var(--ql-border);
}

.section-title {
	font-size: 0.9375rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0;
}

.chevron {
	width: 1.25rem;
	height: 1.25rem;
	color: var(--ql-text-muted);
	transition: transform 0.2s ease;
}

.chevron.rotated {
	transform: rotate(180deg);
}

.section-content {
	padding: 1rem;
	font-size: 0.875rem;
	line-height: 1.7;
	color: var(--ql-text);
	max-height: 300px;
	overflow-y: auto;
}

.section-content :deep(p) {
	margin-bottom: 0.75rem;
}

.section-content :deep(h1),
.section-content :deep(h2),
.section-content :deep(h3) {
	font-weight: 600;
	margin-top: 1rem;
	margin-bottom: 0.5rem;
}

.section-content :deep(ul),
.section-content :deep(ol) {
	margin-bottom: 0.75rem;
	padding-left: 1.5rem;
}

.section-content :deep(li) {
	margin-bottom: 0.25rem;
}

.terms-meta {
	display: flex;
	align-items: center;
	gap: 1rem;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	padding-top: 0.5rem;
}

/* Footer */
.modal-footer {
	padding: 1.25rem 1.5rem;
	border-top: 1px solid var(--ql-border);
	display: flex;
	flex-direction: column;
	gap: 1rem;
}

.checkbox-wrapper {
	display: flex;
	align-items: flex-start;
	gap: 0.75rem;
	cursor: pointer;
}

.terms-checkbox {
	width: 1.25rem;
	height: 1.25rem;
	margin-top: 0.125rem;
	accent-color: var(--ql-accent);
	cursor: pointer;
}

.checkbox-label {
	font-size: 0.9375rem;
	color: var(--ql-text);
	line-height: 1.4;
}

.footer-actions {
	display: flex;
	justify-content: flex-end;
	gap: 0.75rem;
}

.cancel-btn {
	padding: 0.625rem 1.25rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
	background: transparent;
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.cancel-btn:hover {
	background-color: var(--ql-subtle);
}

.accept-btn {
	padding: 0.625rem 1.5rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: white;
	background-color: var(--ql-accent);
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.accept-btn:hover:not(:disabled) {
	background-color: var(--ql-accent-hover);
}

.accept-btn:disabled {
	opacity: 0.5;
	cursor: not-allowed;
}

.btn-loading {
	display: flex;
	align-items: center;
	gap: 0.5rem;
}

.spinner-small {
	width: 1rem;
	height: 1rem;
	border: 2px solid rgba(255, 255, 255, 0.3);
	border-top-color: white;
	border-radius: 50%;
	animation: spin 0.8s linear infinite;
}

/* Mobile Adjustments */
@media (max-width: 640px) {
	.terms-modal-container {
		max-height: 95vh;
	}

	.modal-header {
		padding: 1rem;
	}

	.modal-body {
		padding: 1rem;
	}

	.modal-footer {
		padding: 1rem;
	}

	.footer-actions {
		flex-direction: column;
	}

	.cancel-btn,
	.accept-btn {
		width: 100%;
		justify-content: center;
	}
}
</style>
