<script setup>
import { computed } from "vue";

const props = defineProps({ percent: { type: Number, default: 80 } });

const RADIUS = 80;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;
const dash = computed(() => {
	const clamped = Math.min(100, Math.max(0, props.percent));
	return `${(CIRCUMFERENCE * clamped) / 100} ${CIRCUMFERENCE}`;
});
</script>

<template>
	<div class="spot-art" aria-hidden="true">
		<span class="coin coin-1"></span>
		<span class="coin coin-2"></span>
		<span class="coin coin-3"></span>
		<svg viewBox="0 0 200 200" class="spot-ring">
			<circle class="ring-track" cx="100" cy="100" :r="RADIUS" />
			<circle
				class="ring-fill"
				cx="100"
				cy="100"
				:r="RADIUS"
				:stroke-dasharray="dash"
				transform="rotate(-90 100 100)"
			/>
		</svg>
	</div>
</template>

<style scoped>
.spot-art {
	position: relative;
	width: 100%;
	height: 100%;
	min-height: 240px;
	display: flex;
	align-items: center;
	justify-content: center;
	overflow: hidden;
	background: linear-gradient(160deg, var(--ql-subtle), var(--ql-accent-soft));
}
.spot-ring {
	width: 62%;
	max-width: 280px;
}
.spot-ring circle {
	fill: none;
	stroke-width: 14;
	stroke-linecap: round;
}
.ring-track {
	stroke: var(--ql-border);
}
.ring-fill {
	stroke: var(--ql-accent);
}
.coin {
	position: absolute;
	bottom: -40px;
	border-radius: 50%;
	background: var(--ql-accent-soft);
	border: 1px solid var(--ql-accent);
	opacity: 0.5;
}
.coin-1 { left: 18%; width: 28px; height: 28px; }
.coin-2 { left: 70%; width: 40px; height: 40px; }
.coin-3 { left: 45%; width: 22px; height: 22px; }

@media (prefers-reduced-motion: no-preference) {
	.coin {
		animation: coin-float 7s ease-in infinite;
	}
	.coin-2 { animation-delay: 2s; }
	.coin-3 { animation-delay: 4s; }
	@keyframes coin-float {
		0% { transform: translateY(0); opacity: 0; }
		15% { opacity: 0.6; }
		100% { transform: translateY(-340px); opacity: 0; }
	}
}
</style>
