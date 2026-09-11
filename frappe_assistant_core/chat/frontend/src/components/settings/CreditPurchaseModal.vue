<template>
	<Teleport to="body">
		<div v-if="isOpen" class="modal-overlay" @click.self="$emit('close')">
			<div class="credit-modal-container">
				<!-- Header -->
				<div class="modal-header">
					<h2 class="modal-title">Buy Prepaid Credits</h2>
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
					<p class="credit-description">
						Prepaid credits are consumed after your monthly quota is exhausted,
						and carry over across billing cycles.
						<template v-if="validityNote">{{ validityNote }}</template>
					</p>

					<CreditAmountPicker
						v-model:credit-amount="creditAmount"
						v-model:selected-gateway="selectedGateway"
						:gateways="gateways"
						:minimum-purchase="minimumPurchase"
						:presets="presets"
					/>

					<CreditPriceSummary
						:credit-amount="creditAmount"
						:pack-credits="activePricing.packCredits"
						:pack-price="activePricing.packPrice"
						:symbol="activePricing.symbol"
						:local-currency="selectedGatewayData?.local_currency || ''"
					/>
					<HostedCheckoutNotice />
				</div>

				<!-- Footer -->
				<div class="modal-footer">
					<button @click="$emit('close')" class="cancel-btn">Cancel</button>
					<button
						@click="handlePurchase"
						:disabled="!canPurchase || isProcessing"
						class="purchase-btn"
					>
						<span v-if="isProcessing" class="btn-loading">
							<div class="spinner-small"></div>
							Processing...
						</span>
						<span v-else>Purchase {{ formattedPrice }}</span>
					</button>
				</div>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import CreditAmountPicker from "./billing/CreditAmountPicker.vue";
import CreditPriceSummary from "./billing/CreditPriceSummary.vue";
import HostedCheckoutNotice from "./billing/HostedCheckoutNotice.vue";

const props = defineProps({
	isOpen: {
		type: Boolean,
		required: true,
	},
	gateways: {
		type: Array,
		default: () => [],
	},
	isProcessing: {
		type: Boolean,
		default: false,
	},
});

const emit = defineEmits(["close", "purchase"]);

const minimumPurchase = 1000;
const presets = [2000, 10000, 50000, 200000];

const creditAmount = ref(10000);
const selectedGateway = ref(null);
const selectedGatewayData = computed(() =>
	props.gateways.find((g) => g.name === selectedGateway.value)
);

function pickGateway(gateways) {
	if (!gateways?.length) return null;
	return gateways.find((g) => g.is_recommended) || gateways[0];
}

// Pricing from the selected gateway — or the recommended one while
// selection is catching up. Never invent a USD pack: that flash is what
// made Indian tenants see "$" until they refreshed.
const activePricing = computed(() => {
	const gw =
		props.gateways.find((g) => g.name === selectedGateway.value) || pickGateway(props.gateways);
	if (gw) {
		const currency = gw.currency || "USD";
		return {
			packCredits: Number(gw.pack_credits || 2000),
			packPrice: Number(gw.pack_price || 0),
			symbol: gw.currency_symbol || (currency === "INR" ? "₹" : "$"),
			currency,
			// Null, never a guessed default. An absent field means this AR
			// predates the validity window, and both possible guesses are a
			// claim about the buyer's money — the same reason the pack price
			// above is never invented.
			validityMonths:
				gw.credit_validity_months === undefined || gw.credit_validity_months === null
					? null
					: Number(gw.credit_validity_months),
		};
	}
	return { packCredits: 2000, packPrice: 0, symbol: "", currency: "", validityMonths: null };
});

// Says nothing at all when the window is unknown. This copy used to promise
// credits "never expire", which stopped being true the day purchases gained
// a validity window — a false statement on the screen that takes the money.
const validityNote = computed(() => {
	const months = activePricing.value.validityMonths;
	if (months === null) return "";
	if (months <= 0) return "They do not expire.";
	return `They stay valid for ${months} month${months === 1 ? "" : "s"} from the date you buy them.`;
});

const calculatedPrice = computed(() => {
	const { packCredits, packPrice } = activePricing.value;
	if (!packCredits || !packPrice) return 0;
	return (creditAmount.value / packCredits) * packPrice;
});

const formattedPrice = computed(() => {
	const p = activePricing.value;
	if (!p.symbol || !p.packPrice) return "…";
	return `${p.symbol}${calculatedPrice.value.toLocaleString(undefined, {
		minimumFractionDigits: 2,
		maximumFractionDigits: 2,
	})}`;
});

const canPurchase = computed(() => {
	return creditAmount.value >= minimumPurchase && selectedGateway.value && !!activePricing.value.packPrice;
});

// Select the recommended gateway whenever the modal opens or gateways
// arrive. Watching only `gateways` missed the reopen case: closing
// clears `selectedGateway`, but a cached gateways array does not change
// reference, so the old watch never re-fired and the USD fallback stuck.
watch(
	() => [props.isOpen, props.gateways],
	([isOpen, gateways]) => {
		if (!isOpen) {
			creditAmount.value = 10000;
			selectedGateway.value = null;
			return;
		}
		if (gateways.length > 0 && !selectedGateway.value) {
			const recommended = pickGateway(gateways);
			selectedGateway.value = recommended?.name || null;
		}
	},
	{ immediate: true }
);

function handlePurchase() {
	if (!canPurchase.value) return;
	emit("purchase", {
		creditAmount: creditAmount.value,
		gateway: selectedGateway.value,
	});
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
	z-index: 1100;
	padding: 1rem;
}

.credit-modal-container {
	background: var(--ql-surface);
	border-radius: 1rem;
	width: 100%;
	max-width: 460px;
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
	display: flex;
	flex-direction: column;
	gap: 1.25rem;
}

.credit-description {
	font-size: 0.875rem;
	color: var(--ql-text-muted);
	margin: 0;
	line-height: 1.5;
}

/* Footer */
.modal-footer {
	padding: 1.25rem 1.5rem;
	border-top: 1px solid var(--ql-border);
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

.purchase-btn {
	padding: 0.625rem 1.5rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: white;
	background-color: #8b5cf6;
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.purchase-btn:hover:not(:disabled) {
	background-color: #7c3aed;
}

.purchase-btn:disabled {
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

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

/* Mobile */
@media (max-width: 480px) {
	.credit-modal-container {
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
	.purchase-btn {
		width: 100%;
		justify-content: center;
	}
}
</style>
