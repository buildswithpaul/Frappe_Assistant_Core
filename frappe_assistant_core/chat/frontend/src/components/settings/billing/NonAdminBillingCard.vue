<template>
	<div>
		<div class="non-admin-card">
			<div class="non-admin-header">
				<div>
					<span class="plan-name">{{ formatPlanName(currentPlan) }}</span>
					<span class="plan-badge" :class="'badge-' + currentPlan.toLowerCase()">
						{{ formatPlanName(currentPlan) }}
					</span>
				</div>
			</div>

			<div class="non-admin-usage">
				<div class="usage-header">
					<span class="usage-label">Credits</span>
					<span class="usage-value">
						{{ formatTokens(quota?.credits_used || quota?.quota_used || 0) }} /
						{{
							quota?.is_unlimited
								? "Unlimited"
								: formatTokens(quota?.credit_quota || quota?.quota_total || 0)
						}}
					</span>
				</div>
				<div class="usage-bar" v-if="!quota?.is_unlimited">
					<div
						class="usage-fill"
						:style="{ width: creditsPercentage + '%', background: usageBarColor }"
					></div>
				</div>
				<div class="usage-percent" v-if="!quota?.is_unlimited">
					{{ Math.round(creditsPercentage) }}% used
				</div>
				<div class="usage-percent" v-else>Development Mode</div>
			</div>
		</div>

		<div class="admin-notice">
			<svg class="notice-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
				/>
			</svg>
			<span>Contact your administrator to manage billing and subscription plans.</span>
		</div>
	</div>
</template>

<script setup>
import { formatTokens, formatPlanName } from "@/composables/useFormatters";

defineProps({
	currentPlan: { type: String, required: true },
	quota: { type: Object, default: null },
	creditsPercentage: { type: Number, default: 0 },
	usageBarColor: { type: String, default: "var(--ql-accent)" },
});
</script>

<style scoped>
.non-admin-card {
	padding: 1.25rem;
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
}

.non-admin-header {
	display: flex;
	justify-content: space-between;
	align-items: center;
	margin-bottom: 1rem;
}

.non-admin-header > div {
	display: flex;
	align-items: center;
	gap: 0.75rem;
}

.plan-name {
	font-size: 1.125rem;
	font-weight: 600;
	color: var(--ql-text);
}

.plan-badge {
	padding: 0.25rem 0.625rem;
	font-size: 0.75rem;
	font-weight: 500;
	text-transform: uppercase;
	border-radius: 9999px;
	letter-spacing: 0.025em;
}

.badge-free,
.badge-development {
	background: var(--ql-subtle);
	color: var(--ql-text-muted);
}
.badge-individual,
.badge-starter {
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
}
.badge-team,
.badge-pro {
	background: rgba(139, 92, 246, 0.1);
	color: #8b5cf6;
}
.badge-organization,
.badge-enterprise {
	background: rgba(245, 158, 11, 0.1);
	color: #f59e0b;
}

.non-admin-usage {
	padding-top: 1rem;
	border-top: 1px solid var(--ql-border);
}

.usage-header {
	display: flex;
	justify-content: space-between;
	align-items: center;
	margin-bottom: 0.5rem;
}

.usage-label {
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
}

.usage-value {
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
}

.usage-bar {
	height: 6px;
	background: var(--ql-border);
	border-radius: 3px;
	overflow: hidden;
	margin-bottom: 0.375rem;
}

.usage-fill {
	height: 100%;
	border-radius: 3px;
	transition: width 0.5s ease, background 0.3s ease;
}

.usage-percent {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.admin-notice {
	display: flex;
	align-items: flex-start;
	gap: 0.625rem;
	padding: 1rem;
	margin-top: 1rem;
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	font-size: 0.875rem;
	color: var(--ql-text-muted);
}

.notice-icon {
	width: 1.25rem;
	height: 1.25rem;
	flex-shrink: 0;
	margin-top: 0.0625rem;
}
</style>
