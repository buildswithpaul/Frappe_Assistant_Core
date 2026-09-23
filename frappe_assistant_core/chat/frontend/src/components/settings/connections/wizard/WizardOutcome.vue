<template>
	<div class="wizard-outcome" :class="`is-${tone}`">
		<span class="wizard-outcome__icon" aria-hidden="true">
			<svg v-if="tone === 'done'" viewBox="0 0 20 20" class="wizard-outcome__glyph">
				<path d="M5.4 10.6 8.6 13.8 14.8 6.9" />
			</svg>
			<span v-else class="wizard-outcome__spinner"></span>
		</span>
		<h3 class="wizard-outcome__title">{{ title }}</h3>
		<p class="wizard-outcome__detail">{{ detail }}</p>
	</div>
</template>

<script setup>
defineProps({
	// "waiting" while the browser is on its way to the authorization server,
	// "done" once the connection exists.
	tone: { type: String, default: "done" },
	title: { type: String, default: "" },
	detail: { type: String, default: "" },
});
</script>

<style scoped>
.wizard-outcome {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 0.375rem;
	padding: var(--ql-space-6) var(--ql-space-2);
	text-align: center;
}

.wizard-outcome__icon {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	width: 2.5rem;
	height: 2.5rem;
	margin-bottom: 0.375rem;
	border-radius: 50%;
}

.wizard-outcome.is-done .wizard-outcome__icon {
	color: var(--ql-success);
	background: color-mix(in srgb, var(--ql-success) 14%, transparent);
}

.wizard-outcome.is-waiting .wizard-outcome__icon {
	color: var(--ql-accent);
	background: var(--ql-accent-soft);
}

.wizard-outcome__glyph {
	width: 1.25rem;
	height: 1.25rem;
	fill: none;
	stroke: currentColor;
	stroke-width: 1.8;
	stroke-linecap: round;
	stroke-linejoin: round;
}

.wizard-outcome__spinner {
	width: 1.125rem;
	height: 1.125rem;
	border: 2px solid color-mix(in srgb, currentColor 30%, transparent);
	border-top-color: currentColor;
	border-radius: 50%;
	animation: wizard-outcome-spin 0.8s linear infinite;
}

.wizard-outcome__title {
	margin: 0;
	font-size: 1rem;
	font-weight: 600;
	line-height: 1.35;
	letter-spacing: -0.01em;
	color: var(--ql-text);
	word-break: break-word;
}

.wizard-outcome__detail {
	max-width: 26rem;
	margin: 0;
	font-size: 0.8125rem;
	line-height: 1.55;
	color: var(--ql-text-secondary);
	word-break: break-word;
}

@keyframes wizard-outcome-spin {
	to {
		transform: rotate(360deg);
	}
}

@media (prefers-reduced-motion: reduce) {
	.wizard-outcome__spinner {
		animation-name: none;
	}
}
</style>
