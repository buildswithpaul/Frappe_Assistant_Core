<template>
	<div class="checking-step">
		<div class="checking-step__intro">
			<div class="checking-step__head">
				<h3 class="checking-step__title">{{ title }}</h3>
				<span v-if="steps.length && !failed" class="checking-step__count">
					{{ done }}/{{ steps.length }}
				</span>
			</div>
			<p v-if="host" class="checking-step__target">{{ host }}</p>
		</div>

		<div
			v-if="running"
			class="checking-step__track"
			role="progressbar"
			aria-label="Running checks"
		>
			<span class="checking-step__beam"></span>
		</div>

		<PreflightSteps
			v-if="steps.length || running"
			:steps="steps"
			:revealed="revealed"
			:running="running"
		/>
	</div>
</template>

<script setup>
import { computed } from "vue";
import PreflightSteps from "./PreflightSteps.vue";

const props = defineProps({
	steps: { type: Array, default: () => [] },
	revealed: { type: Number, default: 0 },
	running: { type: Boolean, default: false },
	host: { type: String, default: "" },
});

const done = computed(() => Math.min(Math.max(0, props.revealed), props.steps.length));

// A settled failure is the end of this step, not progress through it — saying
// "Checking the server, 4/4" over a red row reads as a success.
const failed = computed(
	() => !props.running && props.steps.slice(0, done.value).some((step) => step.status === "fail")
);

const title = computed(() => (failed.value ? "This server didn't pass" : "Checking the server"));
</script>

<style scoped>
.checking-step {
	display: flex;
	flex-direction: column;
	gap: var(--ql-space-3);
}

.checking-step__intro {
	display: flex;
	flex-direction: column;
	gap: 0.25rem;
}

.checking-step__head {
	display: flex;
	align-items: baseline;
	justify-content: space-between;
	gap: 0.5rem;
}

.checking-step__title {
	margin: 0;
	font-size: 1.0625rem;
	font-weight: 600;
	line-height: 1.3;
	letter-spacing: -0.01em;
	color: var(--ql-text);
}

.checking-step__count {
	flex: none;
	font-variant-numeric: tabular-nums;
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-text-muted);
}

.checking-step__target {
	margin: 0;
	font-family: var(--ql-font-mono);
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	word-break: break-all;
}

.checking-step__track {
	position: relative;
	height: 3px;
	overflow: hidden;
	border-radius: 9999px;
	background: var(--ql-subtle);
}

.checking-step__beam {
	position: absolute;
	inset-block: 0;
	width: 40%;
	border-radius: inherit;
	background: var(--ql-accent);
	animation: checking-step-sweep 1.4s ease-in-out infinite;
}

@keyframes checking-step-sweep {
	0% {
		left: -40%;
	}
	100% {
		left: 100%;
	}
}

@media (prefers-reduced-motion: reduce) {
	.checking-step__beam {
		animation-name: none;
		left: 0;
		width: 100%;
		opacity: 0.5;
	}
}
</style>
