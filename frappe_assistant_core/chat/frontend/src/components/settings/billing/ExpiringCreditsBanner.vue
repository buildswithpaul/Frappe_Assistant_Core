<template>
	<div v-if="visibleBatches.length" class="expiring-banner-stack">
		<div
			v-for="batch in visibleBatches"
			:key="batch.name"
			class="expiring-banner"
			:class="{ urgent: (batch.days_remaining || 0) <= 1 }"
		>
			<div class="expiring-content">
				<span class="expiring-icon" aria-hidden="true">⚠</span>
				<span class="expiring-text">
					<strong>
						{{ formatCredits(batch.credits_remaining) }}
						{{ batch.source }} credits
					</strong>
					expire in
					<strong>
						{{ batch.days_remaining }} day{{ batch.days_remaining === 1 ? "" : "s" }}
					</strong>
					({{ formatDate(batch.expires_at) }}).
				</span>
			</div>
			<button class="expiring-dismiss" @click="dismiss(batch.name)" aria-label="Dismiss">
				×
			</button>
		</div>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";

const DISMISS_KEY = "faco_expiring_credits_dismissed";

const batches = ref([]);
const dismissed = ref(new Set());

function loadDismissed() {
	try {
		const stored = JSON.parse(localStorage.getItem(DISMISS_KEY) || "[]");
		dismissed.value = new Set(stored);
	} catch (_) {
		dismissed.value = new Set();
	}
}

function persistDismissed() {
	try {
		localStorage.setItem(DISMISS_KEY, JSON.stringify([...dismissed.value]));
	} catch (_) {
		/* ignore */
	}
}

async function loadBatches() {
	try {
		const result = await api.billing.getExpiringCredits();
		if (result?.error) {
			logger.warn("Failed to load expiring credits:", result.error);
			batches.value = [];
			return;
		}
		batches.value = result?.batches || [];
	} catch (e) {
		logger.warn("Failed to load expiring credits:", e);
		batches.value = [];
	}
}

const visibleBatches = computed(() => batches.value.filter((b) => !dismissed.value.has(b.name)));

function dismiss(name) {
	dismissed.value.add(name);
	persistDismissed();
}

function formatCredits(n) {
	const v = Number(n || 0);
	return Math.round(v).toLocaleString();
}

function formatDate(iso) {
	if (!iso) return "—";
	try {
		return new Date(iso).toLocaleDateString(undefined, {
			year: "numeric",
			month: "short",
			day: "numeric",
		});
	} catch (_) {
		return String(iso);
	}
}

onMounted(() => {
	loadDismissed();
	loadBatches();
});
</script>

<style scoped>
.expiring-banner-stack {
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
	margin-bottom: 1rem;
}

.expiring-banner {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 0.75rem 1rem;
	background: #fef3c7;
	border: 1px solid #fcd34d;
	border-radius: 0.5rem;
	color: #78350f;
	font-size: 0.875rem;
}

.expiring-banner.urgent {
	background: #fee2e2;
	border-color: #fca5a5;
	color: #7f1d1d;
}

.expiring-content {
	display: flex;
	align-items: center;
	gap: 0.5rem;
}

.expiring-icon {
	font-size: 1.125rem;
}

.expiring-dismiss {
	background: transparent;
	border: 0;
	color: inherit;
	font-size: 1.25rem;
	line-height: 1;
	cursor: pointer;
	padding: 0 0.5rem;
	opacity: 0.6;
}

.expiring-dismiss:hover {
	opacity: 1;
}
</style>
