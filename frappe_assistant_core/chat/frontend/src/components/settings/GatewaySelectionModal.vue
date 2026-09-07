<template>
	<Teleport to="body">
		<div v-if="isOpen" class="modal-overlay" @click.self="$emit('close')">
			<div class="gateway-modal-container">
				<!-- Header -->
				<div class="modal-header">
					<div class="header-text">
						<h2 class="modal-title">Select Payment Method</h2>
						<p class="modal-subtitle">
							<span class="plan-chip">{{ planName }}</span>
							<span class="dot-sep">•</span>
							{{ billingCycle === "annual" ? "Annual" : "Monthly" }} billing
						</p>
					</div>
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
						<span>Loading payment options...</span>
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
						<p class="error-title">Failed to load payment options</p>
						<p class="error-description">{{ error }}</p>
						<button @click="$emit('close')" class="retry-btn">Close</button>
					</div>

					<!-- Gateway Options -->
					<div v-else class="gateway-content">
						<div class="gateway-grid">
							<GatewayCard
								v-for="gateway in gateways"
								:key="gateway.name"
								:gateway="gateway"
								:selected="selectedGateway === gateway.name"
								:billing-cycle="billingCycle"
								:plan-id="planId"
								:plan-name="planName"
								@select="selectedGateway = $event"
							/>
						</div>

						<!-- Billing identity summary — already captured via
                 Billing Details tab, so we just confirm what will be
                 sent to the gateway. -->
						<div v-if="billingEmail" class="billing-summary">
							<svg
								class="summary-icon"
								viewBox="0 0 24 24"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									d="M5 13l4 4L19 7"
								/>
							</svg>
							<div class="summary-text">
								<div class="summary-line">
									Billing to <strong>{{ billingEmail }}</strong>
								</div>
								<button
									type="button"
									class="edit-link"
									@click="$emit('edit-billing-details')"
								>
									Edit billing details
								</button>
							</div>
						</div>

						<!-- Promo Code -->
						<PromoCodeSection
							:applied-promo="appliedPromo"
							:promo-error="promoError"
							:validating-promo="validatingPromo"
							@validate-promo="$emit('validate-promo', $event)"
							@remove-promo="$emit('remove-promo')"
						/>
					</div>
				</div>

				<!-- Footer -->
				<div v-if="!isLoading && !error" class="modal-footer">
					<button @click="$emit('close')" class="cancel-btn">Cancel</button>
					<button
						@click="handleContinue"
						:disabled="!canContinue || isProcessing"
						class="continue-btn"
					>
						<span v-if="isProcessing" class="btn-loading">
							<div class="spinner-small"></div>
							Processing...
						</span>
						<span v-else>Continue to Payment</span>
					</button>
				</div>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
import { ref, watch, computed } from "vue";
import GatewayCard from "./billing/GatewayCard.vue";
import PromoCodeSection from "./billing/PromoCodeSection.vue";

const props = defineProps({
	isOpen: { type: Boolean, required: true },
	gateways: { type: Array, default: () => [] },
	planName: { type: String, default: "" },
	planId: { type: String, default: "" },
	billingCycle: { type: String, default: "monthly" },
	isLoading: { type: Boolean, default: false },
	error: { type: String, default: null },
	isProcessing: { type: Boolean, default: false },
	// Read-only billing identity (sourced from the ERPNext Customer +
	// Address saved via the Billing Details tab). Shown as a summary chip
	// so the user can confirm what's on file before paying.
	billingName: { type: String, default: "" },
	billingEmail: { type: String, default: "" },
	appliedPromo: { type: Object, default: null },
	promoError: { type: String, default: null },
	validatingPromo: { type: Boolean, default: false },
});

const emit = defineEmits([
	"close",
	"select",
	"validate-promo",
	"remove-promo",
	"edit-billing-details",
]);

const selectedGateway = ref(null);

const canContinue = computed(() => !!selectedGateway.value);

// Auto-select recommended gateway when data loads
watch(
	() => props.gateways,
	(newGateways) => {
		if (newGateways.length > 0 && !selectedGateway.value) {
			const recommended = newGateways.find((g) => g.is_recommended);
			selectedGateway.value = recommended ? recommended.name : newGateways[0].name;
		}
	},
	{ immediate: true }
);

watch(
	() => props.isOpen,
	(isOpen) => {
		if (!isOpen) selectedGateway.value = null;
	}
);

function handleContinue() {
	if (!canContinue.value) return;
	emit("select", {
		gateway: selectedGateway.value,
		billingName: props.billingName || null,
		billingEmail: props.billingEmail || null,
	});
}
</script>

<style scoped>
.modal-overlay {
	position: fixed;
	inset: 0;
	background-color: rgba(0, 0, 0, 0.55);
	backdrop-filter: blur(4px);
	display: flex;
	align-items: center;
	justify-content: center;
	z-index: 1100;
	padding: 1rem;
}

.gateway-modal-container {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 1rem;
	width: 100%;
	max-width: 520px;
	max-height: 90vh;
	display: flex;
	flex-direction: column;
	box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.25), 0 10px 10px -5px rgba(0, 0, 0, 0.1);
	overflow: hidden;
}

.modal-header {
	display: flex;
	align-items: flex-start;
	justify-content: space-between;
	gap: 0.75rem;
	padding: 1.15rem 1.5rem;
	border-bottom: 1px solid var(--ql-border);
	background: var(--ql-bg);
}
.header-text {
	display: flex;
	flex-direction: column;
	gap: 0.25rem;
	min-width: 0;
}
.modal-title {
	font-size: 1.05rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0;
	line-height: 1.2;
}
.modal-subtitle {
	font-size: 0.8rem;
	color: var(--ql-text-muted);
	margin: 0;
	display: flex;
	align-items: center;
	gap: 0.4rem;
	flex-wrap: wrap;
}
.plan-chip {
	display: inline-flex;
	align-items: center;
	padding: 0.1rem 0.55rem;
	font-size: 0.72rem;
	font-weight: 600;
	text-transform: uppercase;
	letter-spacing: 0.03em;
	color: var(--ql-accent);
	background: var(--ql-accent-soft);
	border-radius: 999px;
}
.dot-sep {
	color: var(--ql-border);
}

.close-btn {
	padding: 0.5rem;
	color: var(--ql-text-muted);
	background: transparent;
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
	flex-shrink: 0;
}
.close-btn:hover {
	background-color: var(--ql-subtle);
	color: var(--ql-text);
}

.modal-body {
	flex: 1;
	overflow-y: auto;
	padding: 1.25rem 1.5rem 1.5rem;
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
	word-break: break-word;
	overflow-wrap: anywhere;
}

.error-icon {
	width: 3rem;
	height: 3rem;
	color: #ef4444;
	flex-shrink: 0;
}

.error-title {
	font-weight: 600;
	color: var(--ql-text);
	margin: 0;
	max-width: 100%;
}

.error-description {
	color: var(--ql-text-muted);
	font-size: 0.875rem;
	margin: 0;
	max-width: 100%;
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

/* Gateway Content */
.gateway-content {
	display: flex;
	flex-direction: column;
	gap: 1.1rem;
}

.gateway-grid {
	display: flex;
	flex-direction: column;
	gap: 0.75rem;
}

/* Billing summary */
.billing-summary {
	display: flex;
	align-items: flex-start;
	gap: 0.65rem;
	padding: 0.8rem 0.95rem;
	background: rgba(16, 185, 129, 0.08);
	border: 1px solid rgba(16, 185, 129, 0.25);
	border-radius: 0.6rem;
}
.summary-icon {
	width: 1.1rem;
	height: 1.1rem;
	color: #10b981;
	margin-top: 0.1rem;
	flex-shrink: 0;
}
.summary-text {
	display: flex;
	flex-direction: column;
	gap: 0.2rem;
	min-width: 0;
	flex: 1;
}
.summary-line {
	font-size: 0.85rem;
	color: var(--ql-text);
	word-break: break-all;
}
.edit-link {
	align-self: flex-start;
	font-size: 0.78rem;
	color: var(--ql-accent);
	background: none;
	border: none;
	padding: 0;
	cursor: pointer;
	text-decoration: underline;
	text-underline-offset: 2px;
}
.edit-link:hover {
	color: var(--ql-accent-hover);
}

/* Footer */
.modal-footer {
	padding: 1rem 1.5rem;
	border-top: 1px solid var(--ql-border);
	background: var(--ql-bg);
	display: flex;
	justify-content: flex-end;
	gap: 0.6rem;
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

.continue-btn {
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

.continue-btn:hover:not(:disabled) {
	background-color: var(--ql-accent-hover);
}

.continue-btn:disabled {
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
@media (max-width: 480px) {
	.gateway-modal-container {
		max-width: 100%;
		margin: 0.5rem;
	}

	.modal-header,
	.modal-body,
	.modal-footer {
		padding: 1rem;
	}

	.modal-footer {
		flex-direction: column;
	}

	.cancel-btn,
	.continue-btn {
		width: 100%;
		justify-content: center;
	}
}
</style>
