<template>
	<div>
		<h3 class="section-title">Registration Status</h3>

		<div class="setting-group">
			<div class="status-card">
				<div class="status-row">
					<span class="status-label">Site Status</span>
					<span :class="['status-badge', statusClass]">
						<span class="status-dot"></span>
						{{ statusLabel }}
					</span>
				</div>
				<div class="status-row" v-if="tenantId">
					<span class="status-label">Tenant ID</span>
					<code class="tenant-id">{{ tenantId }}</code>
				</div>
				<div v-if="canRebind && showRebindAction" class="status-row">
					<span class="status-label">Tenant Secret</span>
					<button type="button" class="rebind-btn" @click="$emit('open-rebind')">
						Rotate secret
					</button>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
	registrationStatus: {
		type: String,
		default: "",
	},
	tenantId: {
		type: String,
		default: "",
	},
	canRebind: {
		type: Boolean,
		default: false,
	},
});

defineEmits(["open-rebind"]);

// Hide the rotate button until the tenant is fully registered — there's no
// secret to rotate yet during not_registered / checking / verification-pending.
const showRebindAction = computed(() => props.registrationStatus === "ready");

const statusClass = computed(() => {
	switch (props.registrationStatus) {
		case "ready":
			return "status-success";
		case "not_registered":
			return "status-warning";
		case "error":
		case "disabled":
			return "status-error";
		default:
			return "status-pending";
	}
});

const statusLabel = computed(() => {
	switch (props.registrationStatus) {
		case "ready":
			return "Registered";
		case "not_registered":
			return "Not Registered";
		case "error":
			return "Error";
		case "disabled":
			return "Disabled";
		case "checking":
			return "Checking...";
		default:
			return props.registrationStatus;
	}
});
</script>

<style scoped>
.section-title {
	font-size: 1rem;
	font-weight: 600;
	color: var(--ql-text);
	margin-bottom: 1rem;
}

.setting-group {
	margin-bottom: 1.5rem;
}

.status-card {
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	padding: 1rem;
}

.status-row {
	display: flex;
	justify-content: space-between;
	align-items: center;
	padding: 0.5rem 0;
}

.status-row:not(:last-child) {
	border-bottom: 1px solid var(--ql-border);
}

.status-label {
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text-muted);
}

.status-badge {
	display: inline-flex;
	align-items: center;
	gap: 0.375rem;
	padding: 0.25rem 0.625rem;
	font-size: 0.75rem;
	font-weight: 500;
	border-radius: 9999px;
}

.status-dot {
	width: 0.5rem;
	height: 0.5rem;
	border-radius: 50%;
}

.status-success {
	background: rgba(34, 197, 94, 0.1);
	color: #16a34a;
}

.status-success .status-dot {
	background: #22c55e;
}

.status-warning {
	background: rgba(234, 179, 8, 0.1);
	color: #ca8a04;
}

.status-warning .status-dot {
	background: #eab308;
}

.status-error {
	background: rgba(239, 68, 68, 0.1);
	color: #dc2626;
}

.status-error .status-dot {
	background: #ef4444;
}

.status-pending {
	background: rgba(107, 114, 128, 0.1);
	color: #6b7280;
}

.status-pending .status-dot {
	background: #6b7280;
}

.tenant-id {
	font-size: 0.75rem;
	font-family: monospace;
	background: var(--ql-subtle);
	padding: 0.25rem 0.5rem;
	border-radius: 0.25rem;
	color: var(--ql-text);
}

.rebind-btn {
	padding: 0.3125rem 0.75rem;
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	cursor: pointer;
	transition: background 0.15s ease, border-color 0.15s ease;
}

.rebind-btn:hover {
	background: var(--ql-subtle);
	border-color: var(--ql-accent);
}
</style>
