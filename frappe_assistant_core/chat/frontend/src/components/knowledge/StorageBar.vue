<template>
	<div v-if="storage" :class="compact ? 'storage-inline' : 'storage-section'">
		<!-- Compact: inline pill for top bar -->
		<template v-if="compact">
			<div class="storage-inline-track">
				<div
					class="storage-inline-fill"
					:style="{ width: pct + '%' }"
					:class="storageBarClass"
				></div>
			</div>
			<span class="storage-inline-label"
				>{{ formatStorageSize(storage.used_mb) }} /
				{{ formatStorageSize(storage.quota_mb) }}</span
			>
		</template>

		<!-- Full: original card layout -->
		<template v-else>
			<div class="storage-bar-container">
				<div class="storage-bar-track">
					<div
						class="storage-bar-fill"
						:style="{ width: pct + '%' }"
						:class="storageBarClass"
					></div>
				</div>
				<div class="storage-info">
					<span class="storage-used">{{ formatStorageSize(storage.used_mb) }} used</span>
					<span class="storage-total"
						>{{ formatStorageSize(storage.quota_mb) }} total</span
					>
				</div>
			</div>
		</template>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { formatStorageSize } from "@/composables/useFormatters";

const props = defineProps({
	storage: { type: Object, default: null },
	compact: { type: Boolean, default: false },
});

const pct = computed(() => Math.min(props.storage?.usage_percentage || 0, 100));

const storageBarClass = computed(() => {
	const p = pct.value;
	if (p >= 90) return "bar-danger";
	if (p >= 70) return "bar-warning";
	return "";
});
</script>

<style scoped>
/* --- Compact inline mode (top bar) --- */
.storage-inline {
	display: inline-flex;
	align-items: center;
	gap: 0.5rem;
}

.storage-inline-track {
	width: 80px;
	height: 4px;
	background: var(--ql-border);
	border-radius: 2px;
	overflow: hidden;
}

.storage-inline-fill {
	height: 100%;
	background: var(--ql-accent);
	border-radius: 2px;
	transition: width 0.3s ease;
}

.storage-inline-fill.bar-warning {
	background: var(--ql-warning);
}
.storage-inline-fill.bar-danger {
	background: var(--ql-danger);
}

.storage-inline-label {
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	white-space: nowrap;
	font-variant-numeric: tabular-nums;
}

/* --- Full card mode (fallback) --- */
.storage-section {
	margin-bottom: 1.5rem;
}

.storage-bar-container {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	padding: 0.75rem 1rem;
}

.storage-bar-track {
	height: 6px;
	background: var(--ql-border);
	border-radius: 3px;
	overflow: hidden;
}

.storage-bar-fill {
	height: 100%;
	background: var(--ql-accent);
	border-radius: 3px;
	transition: width 0.3s ease;
}

.storage-bar-fill.bar-warning {
	background: var(--ql-warning);
}
.storage-bar-fill.bar-danger {
	background: var(--ql-danger);
}

.storage-info {
	display: flex;
	justify-content: space-between;
	margin-top: 0.375rem;
	font-size: 0.75rem;
}

.storage-used {
	color: var(--ql-text-secondary);
}
.storage-total {
	color: var(--ql-text-muted);
}
</style>
