<template>
	<div v-if="visible" class="welcome-stage" aria-hidden="true">
		<div class="welcome-backdrop"></div>
		<div class="welcome-robot">
			<FacoRobot size="lg" mood="excited" show-arms show-shadow />
		</div>
		<div class="welcome-text">
			<h1 class="welcome-title">You're all set!</h1>
			<p class="welcome-subtitle">Welcome aboard — let's get started.</p>
		</div>
	</div>
</template>

<script setup>
import FacoRobot from "@/components/common/FacoRobot.vue";

defineProps({
	visible: { type: Boolean, default: false },
});
</script>

<style scoped>
.welcome-stage {
	position: fixed;
	inset: 0;
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	z-index: 100;
	overflow: hidden;
	pointer-events: none;
}

.welcome-backdrop {
	position: absolute;
	inset: 0;
	background: var(--ql-surface);
	animation: welcome-fade-in 0.25s ease forwards;
}

.welcome-robot {
	position: relative;
	animation: robot-fly-in 1.2s cubic-bezier(0.22, 1, 0.36, 1) forwards,
		robot-bounce 0.6s ease 1.2s 1 forwards;
	margin-bottom: 1.5rem;
	z-index: 1;
}

.welcome-text {
	position: relative;
	text-align: center;
	opacity: 0;
	animation: welcome-text-in 0.5s ease 1.4s forwards;
	z-index: 1;
}

.welcome-title {
	font-family: var(--ql-font-serif);
	font-size: 2rem;
	font-weight: 700;
	color: var(--ql-accent);
	margin: 0 0 0.5rem;
}

.welcome-subtitle {
	font-size: 1rem;
	color: var(--ql-text-muted);
	margin: 0;
}

@keyframes robot-fly-in {
	from {
		transform: translate(-60vw, 0) rotate(-12deg);
		opacity: 0;
	}
	to {
		transform: translate(0, 0) rotate(0);
		opacity: 1;
	}
}

@keyframes robot-bounce {
	0% {
		transform: translate(0, 0);
	}
	35% {
		transform: translate(0, -22px);
	}
	65% {
		transform: translate(0, 0);
	}
	85% {
		transform: translate(0, -8px);
	}
	100% {
		transform: translate(0, 0);
	}
}

@keyframes welcome-fade-in {
	from {
		opacity: 0;
	}
	to {
		opacity: 1;
	}
}

@keyframes welcome-text-in {
	from {
		opacity: 0;
		transform: translateY(12px);
	}
	to {
		opacity: 1;
		transform: translateY(0);
	}
}
</style>
