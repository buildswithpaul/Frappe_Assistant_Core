<template>
	<section class="ix-card" :class="{ 'ix-waiting': !decided }" :aria-label="title">
		<header class="ix-head">
			<span class="ix-icon" aria-hidden="true">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
					<path v-for="(d, i) in ICONS[icon] || ICONS.action" :key="i" :d="d" />
				</svg>
			</span>
			<div class="ix-heading">
				<!-- approval-title / approval-subtitle stay as hooks for the QA and film drivers -->
				<h3 class="ix-title approval-title">{{ title }}</h3>
				<div v-if="subtitle" class="ix-subtitle approval-subtitle">{{ subtitle }}</div>
			</div>
			<span v-if="!decided" class="ix-status" data-test="ix-waiting">
				<span class="ix-dot" aria-hidden="true"></span>
				<span class="ix-status-text">{{ __("Waiting for you") }}</span>
			</span>
		</header>
		<div class="ix-body">
			<slot />
		</div>
		<footer v-if="$slots.actions" class="ix-actions">
			<slot name="actions" />
		</footer>
	</section>
</template>

<script setup>
import { __ } from "@/utils/i18n";

defineProps({
	title: { type: String, required: true },
	subtitle: { type: String, default: "" },
	// create | update | delete | action | golive | plan | message
	icon: { type: String, default: "action" },
	decided: { type: Boolean, default: false },
});

// One stroke family (Lucide geometry), drawn at 16px.
const ICONS = {
	create: ["M12 5v14", "M5 12h14"],
	update: ["M12 20h9", "M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"],
	delete: ["M3 6h18", "M8 6V4h8v2", "M19 6l-1 14H6L5 6", "M10 11v6", "M14 11v6"],
	action: ["M20 6 9 17l-5-5"],
	golive: ["M12 2v10", "M18.4 6.6a9 9 0 1 1-12.8 0"],
	plan: ["M9 6h11", "M9 12h11", "M9 18h11", "M4 6h.01", "M4 12h.01", "M4 18h.01"],
	message: ["M4 4h16v16H4z", "m22 6-10 7L2 6"],
};
</script>

<style src="./interactionButtons.css"></style>

<style scoped>
.ix-card {
	container-type: inline-size;
	margin: 8px 0;
	border-radius: var(--ql-radius-xl, 12px);
	border: 1px solid var(--ql-border);
	background: var(--ql-surface);
	overflow: hidden;
}

/* The one attention signal: a gold edge while the card waits on the user (gold = consequence). */
.ix-waiting {
	border-color: color-mix(in srgb, var(--ql-gold) 45%, var(--ql-border));
	box-shadow: 0 1px 3px rgba(26, 26, 23, 0.06);
}

.ix-head {
	display: flex;
	align-items: flex-start;
	gap: 12px;
	padding: 14px 16px 12px;
}

.ix-icon {
	flex-shrink: 0;
	display: flex;
	align-items: center;
	justify-content: center;
	width: 28px;
	height: 28px;
	border-radius: var(--ql-radius-md, 8px);
	background: var(--ql-gold-soft);
	color: var(--ql-warning);
}

.ix-card:not(.ix-waiting) .ix-icon {
	background: var(--ql-subtle);
	color: var(--ql-text-muted);
}

.ix-icon svg {
	width: 16px;
	height: 16px;
}

.ix-heading {
	flex: 1;
	min-width: 0;
	padding-top: 1px;
}

.ix-title {
	margin: 0;
	font-size: 14px;
	font-weight: 600;
	line-height: 1.35;
	color: var(--ql-text);
	overflow-wrap: anywhere;
	text-wrap: balance;
}

.ix-subtitle {
	margin: 3px 0 0;
	font-size: 12.5px;
	line-height: 1.45;
	color: var(--ql-text-secondary);
}

.ix-status {
	flex-shrink: 0;
	display: inline-flex;
	align-items: center;
	gap: 6px;
	margin-top: 5px;
	font-size: 12px;
	color: var(--ql-text-muted);
	white-space: nowrap;
}

.ix-dot {
	width: 7px;
	height: 7px;
	border-radius: 50%;
	background: var(--ql-gold);
}

.ix-body:empty {
	display: none;
}

.ix-actions {
	display: flex;
	flex-wrap: wrap;
	align-items: center;
	gap: 8px;
	padding: 4px 16px 14px;
}

/* Narrow cards (phone, Desk widget) keep the dot and drop the words. */
@container (max-width: 380px) {
	.ix-status-text {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip-path: inset(50%);
	}
}
</style>
