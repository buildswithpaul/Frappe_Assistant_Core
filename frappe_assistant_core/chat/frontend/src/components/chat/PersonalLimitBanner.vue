<template>
	<div class="plb" role="status" data-test="personal-limit-banner">
		<svg class="plb-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
			<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
		</svg>
		<div class="plb-body">
			<p class="plb-text">
				{{
					isAdmin
						? __("You've reached your personal monthly limit. You can change it in Settings → Users (0 means no personal limit).")
						: __("You've reached your personal monthly limit. Ask your team admin to raise it.")
				}}
			</p>
			<p v-if="limit" class="plb-meta">
				{{ __("{0} of {1} credits used this month", [formatCredits(used), formatCredits(limit)]) }}
			</p>
			<router-link v-if="isAdmin" :to="{ name: 'settings-users' }" class="plb-link" data-test="change-limit">
				{{ __("Change limit") }}
			</router-link>
		</div>
	</div>
</template>

<script setup>
import { formatCredits } from "@/composables/useFormatters";
import { __ } from "@/utils/i18n";

// The same words wherever the personal limit stops a chat: the Desk widget's composer, and the
// banner a refused turn (user_limit_reached) shows in both FAC Chat and the widget.
defineProps({
	isAdmin: { type: Boolean, default: false },
	used: { type: Number, default: 0 },
	limit: { type: Number, default: 0 },
});
</script>

<style scoped>
.plb {
	display: flex;
	gap: 10px;
	margin: 0 12px 8px;
	padding: 10px 12px;
	border: 1px solid color-mix(in srgb, var(--ql-gold) 40%, var(--ql-border));
	border-radius: var(--ql-radius-lg, 10px);
	background: var(--ql-gold-soft);
}

.plb-icon {
	flex-shrink: 0;
	width: 16px;
	height: 16px;
	margin-top: 1px;
	color: var(--ql-gold);
}

.plb-body {
	min-width: 0;
}

.plb-text {
	margin: 0;
	font-size: 13px;
	line-height: 1.45;
	color: var(--ql-text);
}

.plb-meta {
	margin: 2px 0 0;
	font-size: 12px;
	color: var(--ql-text-secondary);
	font-variant-numeric: tabular-nums;
}

.plb-link {
	display: inline-block;
	margin-top: 4px;
	font-size: 13px;
	font-weight: 600;
	color: var(--ql-accent);
	text-decoration: underline;
	text-underline-offset: 2px;
}

.plb-link:focus-visible {
	outline: 2px solid var(--ql-accent);
	outline-offset: 2px;
	border-radius: 2px;
}
</style>
