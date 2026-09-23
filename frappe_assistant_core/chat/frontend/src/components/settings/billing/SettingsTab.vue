<template>
	<div class="settings-tab">
		<!-- Payment Methods -->
		<div class="settings-section">
			<h3 class="section-title">Payment Methods</h3>
			<p class="section-description">
				Review the instrument on file for automatic renewals, and change it when
				you need to.
			</p>
			<button
				class="manage-payment-btn"
				@click="$emit('manage-payment')"
			>
				<svg class="btn-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"
					/>
				</svg>
				Go to Payment Method
			</button>
		</div>

		<!-- Partner Attribution (read-only, set at registration) -->
		<div v-if="referral" class="settings-section">
			<h3 class="section-title">Partner Attribution</h3>
			<p class="section-description">
				This account was referred by a partner. Attribution is set during registration and
				cannot be changed.
			</p>
			<div class="referral-card">
				<div class="referral-info">
					<div class="referral-partner">{{ referral.partner_name }}</div>
					<div class="referral-code">{{ referral.referral_code }}</div>
				</div>
				<svg
					class="referral-lock"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					:aria-label="lockTooltip"
					role="img"
				>
					<title>{{ lockTooltip }}</title>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
					/>
				</svg>
			</div>
		</div>

		<!-- Danger Zone -->
		<div class="settings-section danger-section" v-if="showDangerZone">
			<h3 class="section-title danger-title">Danger Zone</h3>
			<div class="danger-card">
				<div class="danger-info">
					<h4>Cancel Subscription</h4>
					<p>
						Your subscription will remain active until the end of the current billing
						period.
					</p>
				</div>
				<button class="danger-btn" @click="$emit('cancel')" :disabled="cancelling">
					{{ cancelling ? "Cancelling..." : "Cancel Subscription" }}
				</button>
			</div>
		</div>
	</div>
</template>

<script setup>
defineProps({
	cancelling: { type: Boolean, default: false },
	showDangerZone: { type: Boolean, default: false },
	referral: {
		type: Object,
		default: null,
	},
});

defineEmits(["manage-payment", "cancel"]);

const lockTooltip = "Set during registration and cannot be changed";
</script>

<style scoped>
.settings-tab {
	display: flex;
	flex-direction: column;
	gap: 1.5rem;
	padding-top: 1.5rem;
}

.settings-section {
	padding-bottom: 1.5rem;
	border-bottom: 1px solid var(--ql-border);
}

.settings-section:last-child {
	border-bottom: none;
	padding-bottom: 0;
}

.section-title {
	font-size: 1rem;
	font-weight: 600;
	color: var(--ql-text);
	margin-bottom: 0.375rem;
}

.section-description {
	font-size: 0.875rem;
	color: var(--ql-text-muted);
	margin-bottom: 1rem;
}

.manage-payment-btn {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.625rem 1rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.manage-payment-btn:hover:not(:disabled) {
	border-color: var(--ql-accent);
	color: var(--ql-accent);
}

.btn-icon {
	width: 1rem;
	height: 1rem;
}

/* Referral card */
.referral-card {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 0.75rem;
	padding: 0.75rem 1rem;
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
}

.referral-info {
	display: flex;
	flex-direction: column;
	gap: 0.125rem;
	min-width: 0;
}

.referral-partner {
	font-size: 0.875rem;
	font-weight: 600;
	color: var(--ql-text);
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.referral-code {
	font-size: 0.75rem;
	font-family: monospace;
	letter-spacing: 0.06em;
	color: var(--ql-text-muted);
}

.referral-lock {
	width: 1rem;
	height: 1rem;
	color: var(--ql-text-muted);
	flex-shrink: 0;
}

/* Danger Zone */
.danger-title {
	color: var(--ql-danger, #ef4444);
}

.danger-card {
	display: flex;
	justify-content: space-between;
	align-items: center;
	padding: 1rem;
	background: var(--ql-bg);
	border: 1px solid rgba(239, 68, 68, 0.2);
	border-radius: 0.5rem;
}

.danger-info h4 {
	font-size: 0.875rem;
	font-weight: 600;
	color: var(--ql-text);
	margin-bottom: 0.25rem;
}

.danger-info p {
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
}

.danger-btn {
	padding: 0.5rem 1rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: white;
	background: var(--ql-danger, #ef4444);
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
	white-space: nowrap;
	flex-shrink: 0;
}

.danger-btn:hover:not(:disabled) {
	opacity: 0.9;
}
.danger-btn:disabled {
	opacity: 0.6;
	cursor: not-allowed;
}

@media (max-width: 640px) {
	.danger-card {
		flex-direction: column;
		align-items: flex-start;
		gap: 1rem;
	}
}
</style>
