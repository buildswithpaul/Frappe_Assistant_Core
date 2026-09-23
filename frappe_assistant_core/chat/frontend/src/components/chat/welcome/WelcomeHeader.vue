<template>
	<header class="wh">
		<div class="wh-text">
			<div class="wh-date">{{ dateLabel }}</div>
			<h1 class="wh-greeting">{{ greeting }}, {{ displayName }}.</h1>
			<p class="wh-sub">What should we work through today?</p>
		</div>
		<FacoRobot size="sm" float show-arms track extra-class="wh-robot" />
	</header>
	<div class="wh-rule" aria-hidden="true"></div>
</template>

<script setup>
import { computed } from "vue";
import FacoRobot from "@/components/common/FacoRobot.vue";
import { formatDateLabel } from "@/components/chat/welcomeGreeting";

defineProps({
	greeting: { type: String, required: true },
	displayName: { type: String, required: true },
});

const dateLabel = computed(() => formatDateLabel(new Date()));
</script>

<style scoped>
.wh { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; }
.wh-text { text-align: left; min-width: 0; }
.wh-date {
	font-size: 11px; font-weight: 600; text-transform: uppercase;
	letter-spacing: 0.08em; color: var(--ql-text-muted);
}
.wh-greeting {
	font-family: var(--ql-font-display);
	/* Homepage masthead: the serif at editorial scale is what anchors the page —
	   typography does the grounding, not a container box. */
	font-size: clamp(34px, 3.6vw, 44px);
	line-height: 1.06; letter-spacing: -0.012em;
	text-wrap: balance;
	color: var(--ql-text); margin: 8px 0 0;
}
.wh-sub { font-size: 15px; color: var(--ql-text-secondary); margin: 8px 0 0; }
.wh-rule {
	height: 2px; margin: 15px 0 0;
	background: linear-gradient(90deg, var(--ql-gold) 0 56px, var(--ql-border) 56px);
}
@media (max-width: 719px) {
	.wh-greeting { font-size: 26px; }
}
</style>
