<template>
	<div class="limit-notice" role="note" data-test="personal-limit-notice">
		<svg class="limit-notice-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
			<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
		</svg>
		<div class="limit-notice-body">
			<p class="limit-notice-title">{{ __("Your personal limit is what's stopping you") }}</p>
			<p class="limit-notice-text">
				{{
					__(
						"You've used {0} of your {1} monthly credits. Prepaid credits go to the team, so buying more won't raise your personal limit.",
						[formatCredits(used), formatCredits(limit)],
					)
				}}
			</p>
			<p class="limit-notice-text">
				{{ __("Change it under Settings, Users, Monthly credit limit. 0 means no personal limit.") }}
			</p>
			<button type="button" class="limit-notice-link" data-test="open-users" @click="$emit('open-users')">
				{{ __("Open Users") }}
			</button>
		</div>
	</div>
</template>

<script setup>
import { formatCredits } from "@/composables/useFormatters";
import { __ } from "@/utils/i18n";

defineProps({
	used: { type: Number, required: true },
	limit: { type: Number, required: true },
});

defineEmits(["open-users"]);
</script>

<style scoped>
.limit-notice {
	display: flex;
	gap: 10px;
	margin-bottom: 16px;
	padding: 12px 14px;
	border: 1px solid color-mix(in srgb, var(--ql-gold) 40%, var(--ql-border));
	border-radius: var(--ql-radius-lg);
	background: var(--ql-gold-soft);
}

.limit-notice-icon {
	flex-shrink: 0;
	width: 18px;
	height: 18px;
	margin-top: 1px;
	color: var(--ql-gold);
}

.limit-notice-body {
	min-width: 0;
}

.limit-notice-title {
	margin: 0 0 4px;
	font-size: 13px;
	font-weight: 600;
	color: var(--ql-text);
}

.limit-notice-text {
	margin: 0 0 4px;
	font-size: 13px;
	line-height: 1.45;
	color: var(--ql-text-secondary);
}

.limit-notice-link {
	margin-top: 4px;
	padding: 0;
	border: 0;
	background: none;
	font: inherit;
	font-size: 13px;
	font-weight: 600;
	color: var(--ql-accent);
	text-decoration: underline;
	text-underline-offset: 2px;
	cursor: pointer;
}

.limit-notice-link:focus-visible {
	outline: 2px solid var(--ql-accent);
	outline-offset: 2px;
	border-radius: 2px;
}
</style>
