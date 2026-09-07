<template>
	<div class="steps-block">
		<div v-if="title" class="steps-title">{{ title }}</div>
		<ol class="steps-list">
			<li
				v-for="(step, idx) in steps"
				:key="idx"
				class="step-item"
				:class="{
					'step-active': current > 0 && idx + 1 === current,
					'step-done': current > 0 && idx + 1 < current,
				}"
			>
				<div class="step-marker">
					<svg
						v-if="current > 0 && idx + 1 < current"
						class="step-check"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2.5"
							d="M5 13l4 4L19 7"
						/>
					</svg>
					<span v-else class="step-number">{{ idx + 1 }}</span>
				</div>
				<div class="step-content" v-html="step"></div>
			</li>
		</ol>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { marked } from "marked";
import DOMPurify from "dompurify";

const props = defineProps({
	title: { type: String, default: "" },
	current: { type: Number, default: 0 },
	body: { type: String, default: "" },
});

const steps = computed(() => {
	if (!props.body) return [];
	return props.body
		.split("\n")
		.map((line) => line.replace(/^\d+\.\s*/, "").trim())
		.filter(Boolean)
		.map((text) => DOMPurify.sanitize(marked.parse(text)));
});
</script>

<style scoped>
.steps-block {
	margin: 0.75rem 0;
	padding: 1rem 1.25rem;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
}

.steps-title {
	font-size: 0.875rem;
	font-weight: 600;
	color: var(--ql-text);
	margin-bottom: 0.75rem;
}

.steps-list {
	list-style: none;
	margin: 0;
	padding: 0;
}

.step-item {
	display: flex;
	gap: 0.75rem;
	position: relative;
	padding-bottom: 1rem;
}

.step-item:last-child {
	padding-bottom: 0;
}

/* Connecting line */
.step-item:not(:last-child)::after {
	content: "";
	position: absolute;
	left: 0.75rem;
	top: 1.75rem;
	bottom: 0;
	width: 2px;
	background: var(--ql-border);
}

.step-item.step-done:not(:last-child)::after {
	background: #22c55e;
}

.step-marker {
	flex-shrink: 0;
	width: 1.5rem;
	height: 1.5rem;
	border-radius: 50%;
	display: flex;
	align-items: center;
	justify-content: center;
	font-size: 0.75rem;
	font-weight: 600;
	background: var(--ql-border);
	color: var(--ql-text-muted);
	position: relative;
	z-index: 1;
}

.step-active .step-marker {
	background: var(--ql-accent);
	color: #fff;
	box-shadow: 0 0 0 3px var(--ql-accent-soft);
}

.step-done .step-marker {
	background: #22c55e;
	color: #fff;
}

.step-check {
	width: 0.875rem;
	height: 0.875rem;
}

.step-number {
	line-height: 1;
}

.step-content {
	flex: 1;
	font-size: 0.8125rem;
	line-height: 1.5;
	color: var(--ql-text);
	padding-top: 0.125rem;
}

.step-content :deep(h1),
.step-content :deep(h2),
.step-content :deep(h3),
.step-content :deep(h4) {
	font-family: var(--ql-font-display);
	font-size: 0.9375rem;
	font-weight: 600;
	letter-spacing: -0.01em;
	color: var(--ql-text);
	margin: 0;
}

.step-content :deep(p) {
	margin: 0;
}

.step-content :deep(p + p) {
	margin-top: 0.375rem;
}

.step-content :deep(ul),
.step-content :deep(ol) {
	margin: 0.25rem 0;
	padding-left: 1.25rem;
}

.step-content :deep(ul) {
	list-style: disc;
}

.step-content :deep(ol) {
	list-style: decimal;
}

.step-content :deep(strong) {
	font-weight: 600;
}
.step-content :deep(code) {
	padding: 0.0625rem 0.25rem;
	background: var(--ql-subtle);
	border-radius: 0.25rem;
	font-size: 0.8em;
}
</style>
