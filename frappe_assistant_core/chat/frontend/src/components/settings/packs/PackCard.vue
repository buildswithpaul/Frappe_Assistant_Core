<template>
	<div class="pack-card">
		<div class="pack-head">
			<span class="pack-icon">{{ pack.icon || "📦" }}</span>
			<div class="pack-meta">
				<div class="pack-title">{{ pack.display_name }}</div>
				<div class="pack-industry">{{ pack.industry || "General" }}</div>
			</div>

			<!-- Owned + purchased → Toggle (works for enable AND disable) -->
			<label
				v-if="pack.is_owned && pack.acquisition === 'purchased'"
				class="toggle"
			>
				<input
					type="checkbox"
					:checked="pack.enabled"
					:disabled="busy"
					@change="onTogglePurchased($event.target.checked)"
				/>
				<span class="slider" />
			</label>

			<!-- Owned + free_grant → badge -->
			<span
				v-else-if="pack.is_owned && pack.acquisition === 'free_grant'"
				class="ownership-badge free-grant"
				>Free Pack</span
			>

			<!-- Owned + admin_grant → badge -->
			<span
				v-else-if="pack.is_owned && pack.acquisition === 'admin_grant'"
				class="ownership-badge gifted"
				>Gifted</span
			>

			<!-- Free grant available -->
			<button
				v-else-if="pack.is_free_grant_available"
				class="activate-btn"
				:disabled="busy"
				@click="onActivateFree"
			>
				Activate (free)
			</button>

			<!-- Requires purchase -->
			<button
				v-else-if="pack.requires_purchase"
				class="buy-btn"
				:disabled="busy"
				@click="onPurchase"
			>
				Buy {{ priceLabel }}
			</button>

			<!-- Not purchasable, not owned -->
			<span v-else class="ownership-badge unavailable">Unavailable</span>
		</div>
		<div class="pack-stats">
			{{ pack.prompt_count }} prompts · {{ pack.skill_count }} skills
		</div>

		<!-- Free-grant confirmation modal -->
		<div
			v-if="showFreeGrantModal"
			class="modal-overlay"
			@click.self="showFreeGrantModal = false"
		>
			<div class="modal">
				<h3>Activate your free pack</h3>
				<p>
					Your plan includes one free pack. This is a permanent choice —
					once activated, you can't switch to a different free pack later.
					Other packs can be purchased individually.
				</p>
				<div class="modal-actions">
					<button class="btn-secondary" @click="showFreeGrantModal = false">
						Cancel
					</button>
					<button class="btn-primary" @click="confirmFreeGrant">
						Activate {{ pack.display_name }}
					</button>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref, computed } from "vue";
import { usePacksStore } from "@/stores/packsStore";
import { logger } from "@/utils/logger";

const props = defineProps({
	pack: { type: Object, required: true },
});
const emit = defineEmits(["refresh"]);
const packsStore = usePacksStore();
const busy = ref(false);
const showFreeGrantModal = ref(false);

const priceLabel = computed(() => {
	if (props.pack.purchase_currency === "INR" && props.pack.price_inr) {
		return `₹${props.pack.price_inr}`;
	}
	if (props.pack.purchase_currency === "USD" && props.pack.price_usd) {
		return `$${props.pack.price_usd}`;
	}
	return "";
});

async function onTogglePurchased(enabled) {
	busy.value = true;
	try {
		await packsStore.togglePurchasedPack(props.pack.pack_id, enabled);
	} finally {
		busy.value = false;
	}
}

function onActivateFree() {
	showFreeGrantModal.value = true;
}

async function confirmFreeGrant() {
	showFreeGrantModal.value = false;
	busy.value = true;
	try {
		await packsStore.activateFreePack(props.pack.pack_id);
		emit("refresh");
	} finally {
		busy.value = false;
	}
}

async function onPurchase() {
	busy.value = true;
	try {
		await packsStore.purchasePack(props.pack.pack_id);
		emit("refresh");
	} catch (e) {
		// Razorpay modal dismissed or verify failed — silent for cancel,
		// logged for other errors.
		if (!e?.message?.includes("cancelled")) {
			logger.error("Pack purchase failed:", e);
		}
	} finally {
		busy.value = false;
	}
}
</script>

<style scoped>
.pack-card {
	border: 1px solid var(--ql-border);
	border-radius: 8px;
	padding: 16px;
	background: var(--ql-surface);
}
.pack-head {
	display: flex;
	align-items: center;
	gap: 12px;
}
.pack-icon {
	font-size: 24px;
}
.pack-meta {
	flex: 1;
	min-width: 0;
}
.pack-title {
	font-weight: 600;
	font-size: 15px;
	color: var(--ql-text);
}
.pack-industry {
	font-size: 12px;
	color: var(--ql-text-muted);
}
.pack-stats {
	margin-top: 12px;
	font-size: 12px;
	color: var(--ql-text-muted);
}
.ownership-badge {
	padding: 4px 8px;
	border-radius: 4px;
	font-size: 11px;
	font-weight: 600;
	text-transform: uppercase;
}
.ownership-badge.free-grant {
	background: var(--ql-accent-soft);
	color: var(--ql-success);
}
.ownership-badge.gifted {
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
}
.ownership-badge.unavailable {
	background: var(--ql-subtle);
	color: var(--ql-text-muted);
}
.activate-btn {
	background: var(--ql-success);
	color: white;
	border: 0;
	padding: 6px 12px;
	border-radius: 6px;
	font-size: 12px;
	cursor: pointer;
}
.activate-btn:disabled {
	opacity: 0.6;
	cursor: not-allowed;
}
.buy-btn {
	background: var(--ql-accent);
	color: white;
	border: 0;
	padding: 6px 12px;
	border-radius: 6px;
	font-size: 12px;
	font-weight: 600;
	cursor: pointer;
}
.buy-btn:disabled {
	opacity: 0.6;
	cursor: not-allowed;
}
.toggle {
	position: relative;
	width: 36px;
	height: 20px;
	cursor: pointer;
}
.toggle input {
	opacity: 0;
	width: 100%;
	height: 100%;
	cursor: pointer;
	position: absolute;
}
.slider {
	position: absolute;
	inset: 0;
	background: var(--ql-border);
	border-radius: 999px;
	transition: background 0.15s;
}
.slider::before {
	content: "";
	position: absolute;
	top: 2px;
	left: 2px;
	width: 16px;
	height: 16px;
	background: white;
	border-radius: 50%;
	transition: transform 0.15s;
}
.toggle input:checked + .slider {
	background: var(--ql-accent);
}
.toggle input:checked + .slider::before {
	transform: translateX(16px);
}
.modal-overlay {
	position: fixed;
	inset: 0;
	background: rgba(0, 0, 0, 0.4);
	display: flex;
	align-items: center;
	justify-content: center;
	z-index: 1000;
}
.modal {
	background: var(--ql-surface);
	border-radius: 8px;
	padding: 24px;
	max-width: 480px;
	box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}
.modal h3 {
	margin: 0 0 12px 0;
	color: var(--ql-text);
}
.modal p {
	color: var(--ql-text-muted);
	line-height: 1.5;
	margin: 0 0 20px 0;
}
.modal-actions {
	display: flex;
	gap: 8px;
	justify-content: flex-end;
}
.btn-secondary {
	background: var(--ql-subtle);
	color: var(--ql-text);
	border: 1px solid var(--ql-border);
	padding: 8px 16px;
	border-radius: 6px;
	cursor: pointer;
}
.btn-primary {
	background: var(--ql-accent);
	color: white;
	border: 0;
	padding: 8px 16px;
	border-radius: 6px;
	font-weight: 600;
	cursor: pointer;
}
</style>
