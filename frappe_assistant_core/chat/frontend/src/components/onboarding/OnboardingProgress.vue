<template>
	<nav class="onboarding-progress" aria-label="Onboarding progress" data-test="onboarding-progress">
		<ol class="steps">
			<li
				v-for="(step, i) in steps"
				:key="step.id"
				class="step"
				:class="{
					active: i === currentIndex,
					done: i < currentIndex,
				}"
				:aria-current="i === currentIndex ? 'step' : undefined"
			>
				<span class="dot" aria-hidden="true"></span>
				<span class="label">{{ step.label }}</span>
			</li>
		</ol>
	</nav>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
	/** features | plan | setup */
	phase: {
		type: String,
		required: true,
		validator: (v) => ["features", "plan", "setup"].includes(v),
	},
});

const steps = [
	{ id: "features", label: "Features" },
	{ id: "plan", label: "Plan" },
	{ id: "setup", label: "Setup" },
];

const currentIndex = computed(() => {
	const idx = steps.findIndex((s) => s.id === props.phase);
	return idx >= 0 ? idx : 0;
});
</script>

<style scoped>
.onboarding-progress {
	width: 100%;
	max-width: 420px;
	margin: 0 auto 1.25rem;
}

.steps {
	display: flex;
	align-items: center;
	justify-content: center;
	gap: 0.5rem;
	list-style: none;
	margin: 0;
	padding: 0;
}

.step {
	display: flex;
	align-items: center;
	gap: 0.35rem;
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-text-muted);
}

.step:not(:last-child)::after {
	content: "";
	display: block;
	width: 1.25rem;
	height: 1px;
	margin-left: 0.5rem;
	background: var(--ql-border);
}

.dot {
	width: 0.5rem;
	height: 0.5rem;
	border-radius: 50%;
	background: var(--ql-border);
}

.step.active {
	color: var(--ql-text);
}

.step.active .dot {
	background: var(--ql-accent);
	box-shadow: 0 0 0 3px color-mix(in srgb, var(--ql-accent) 25%, transparent);
}

.step.done {
	color: var(--ql-text-muted);
}

.step.done .dot {
	background: var(--ql-accent);
}

.label {
	white-space: nowrap;
}
</style>
