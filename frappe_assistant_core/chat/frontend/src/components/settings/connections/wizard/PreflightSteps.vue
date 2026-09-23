<template>
	<div class="preflight" :class="{ 'is-collapsible': collapsible }">
		<button
			v-if="collapsible"
			type="button"
			class="preflight__summary"
			:class="{ 'is-open': listVisible }"
			data-test="preflight-summary"
			:aria-expanded="listVisible"
			@click="open = !open"
		>
			<span class="preflight__seal" :class="`is-${verdict}`" aria-hidden="true">
				<svg viewBox="0 0 12 12" class="preflight__seal-glyph">
					<path v-if="verdict === 'fail'" d="M3.2 3.2 8.8 8.8M8.8 3.2 3.2 8.8" />
					<path v-else d="M2.6 6.3 4.9 8.6 9.4 3.6" />
				</svg>
			</span>
			<span class="preflight__tally">{{ tally }}</span>
			<svg viewBox="0 0 12 12" class="preflight__chevron" aria-hidden="true">
				<path d="M3.5 4.5 6 7.2 8.5 4.5" />
			</svg>
		</button>

		<ul v-show="listVisible" class="preflight__list" data-test="preflight-steps">
			<li
				v-for="step in shown"
				:key="step.key"
				class="preflight__row"
				:class="`is-${step.status}`"
				data-test="preflight-step"
			>
				<span
					class="preflight__mark"
					data-test="preflight-mark"
					:data-status="step.status"
					aria-hidden="true"
				>
					<svg viewBox="0 0 12 12" class="preflight__glyph">
						<path v-if="step.status === 'pass'" d="M2.6 6.3 4.9 8.6 9.4 3.6" />
						<path v-else-if="step.status === 'fail'" d="M3.2 3.2 8.8 8.8M8.8 3.2 3.2 8.8" />
						<path v-else d="M3 6h6" />
					</svg>
				</span>

				<span class="preflight__body">
					<span class="preflight__line">
						<span class="preflight__label">{{ step.label }}</span>
						<em v-if="step.status === 'skipped'" class="preflight__tag">skipped</em>
						<span v-if="step.detail" class="preflight__detail">{{ step.detail }}</span>
					</span>
					<span v-if="step.next_action" class="preflight__next" data-test="next-action">
						{{ step.next_action }}
					</span>
				</span>
			</li>

			<li v-if="running" class="preflight__row is-running" data-test="preflight-running">
				<span class="preflight__mark" aria-hidden="true">
					<span class="preflight__pulse"></span>
				</span>
				<span class="preflight__label">Checking…</span>
			</li>
		</ul>
	</div>
</template>

<script setup>
import { computed, ref } from "vue";

const props = defineProps({
	steps: { type: Array, default: () => [] },
	revealed: { type: Number, default: 0 },
	running: { type: Boolean, default: false },
	// Reassurance, not content: once the verdict is in, the rows fold behind a
	// one-line tally so the step's real headline and action can lead.
	collapsible: { type: Boolean, default: false },
});

const open = ref(false);

// `revealed` is a reveal cursor over rows that already carry a verdict, not a
// count of pending placeholders. A row is never drawn before it has a result.
const shown = computed(() => props.steps.slice(0, Math.max(0, props.revealed)));

const counts = computed(() => {
	const tally = { pass: 0, fail: 0, skipped: 0 };
	for (const step of shown.value) {
		if (step.status in tally) tally[step.status] += 1;
	}
	return tally;
});

const verdict = computed(() => (counts.value.fail ? "fail" : "pass"));

// A failure is never something to fold away, whatever the caller asked for.
const listVisible = computed(() => !props.collapsible || open.value || verdict.value === "fail");

const tally = computed(() => {
	const { pass, fail, skipped } = counts.value;
	if (fail) return `${fail} ${fail === 1 ? "check" : "checks"} failed`;
	if (skipped) return `${pass} ${pass === 1 ? "check" : "checks"} passed, ${skipped} skipped`;
	return `All ${pass} ${pass === 1 ? "check" : "checks"} passed`;
});
</script>

<style scoped>
.preflight {
	display: flex;
	flex-direction: column;
}

.preflight__summary {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	width: 100%;
	padding: 0.5rem 0.625rem;
	background: none;
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-md);
	font: inherit;
	text-align: left;
	cursor: pointer;
}

.preflight__summary:hover {
	background: var(--ql-subtle);
	border-color: var(--ql-border-hover);
}

.preflight__summary.is-open {
	border-bottom-left-radius: 0;
	border-bottom-right-radius: 0;
}

.preflight__seal {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	flex: none;
	width: 1.125rem;
	height: 1.125rem;
	border-radius: 50%;
}

.preflight__seal.is-pass {
	color: var(--ql-success);
	background: color-mix(in srgb, var(--ql-success) 14%, transparent);
}

.preflight__seal.is-fail {
	color: var(--ql-danger);
	background: color-mix(in srgb, var(--ql-danger) 14%, transparent);
}

.preflight__seal-glyph,
.preflight__glyph {
	width: 0.75rem;
	height: 0.75rem;
	fill: none;
	stroke: currentColor;
	stroke-width: 1.7;
	stroke-linecap: round;
	stroke-linejoin: round;
}

.preflight__tally {
	flex: 1;
	min-width: 0;
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-text-secondary);
}

.preflight__chevron {
	flex: none;
	width: 0.75rem;
	height: 0.75rem;
	fill: none;
	stroke: var(--ql-text-muted);
	stroke-width: 1.5;
	stroke-linecap: round;
	stroke-linejoin: round;
	transition: transform 150ms ease;
}

.preflight__summary.is-open .preflight__chevron {
	transform: rotate(180deg);
}

.preflight__list {
	display: flex;
	flex-direction: column;
	margin: 0;
	padding: 0;
	list-style: none;
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-md);
}

.preflight.is-collapsible .preflight__list {
	border-top: none;
	border-top-left-radius: 0;
	border-top-right-radius: 0;
	background: var(--ql-subtle);
}

.preflight__row {
	display: flex;
	align-items: baseline;
	gap: 0.5rem;
	padding: 0.375rem 0.625rem;
}

.preflight__row + .preflight__row {
	border-top: 1px solid var(--ql-border);
}

.preflight__mark {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	flex: none;
	width: 0.875rem;
	height: 0.875rem;
	color: var(--ql-text-muted);
	transform: translateY(0.125rem);
}

.preflight__row.is-pass .preflight__mark {
	color: var(--ql-success);
}

.preflight__row.is-fail .preflight__mark {
	color: var(--ql-danger);
}

.preflight__row.is-skipped .preflight__mark {
	opacity: 0.5;
}

.preflight__pulse {
	width: 0.5rem;
	height: 0.5rem;
	border-radius: 50%;
	background: var(--ql-accent);
	animation: preflight-pulse 1.1s ease-in-out infinite;
}

.preflight__body {
	display: flex;
	flex-direction: column;
	gap: 0.1875rem;
	min-width: 0;
}

.preflight__line {
	display: flex;
	align-items: baseline;
	flex-wrap: wrap;
	gap: 0.375rem;
	min-width: 0;
}

.preflight__label {
	font-size: 0.75rem;
	color: var(--ql-text-secondary);
}

.preflight__row.is-fail .preflight__label {
	font-weight: 600;
	color: var(--ql-text);
}

.preflight__row.is-skipped .preflight__label {
	color: var(--ql-text-muted);
}

.preflight__tag {
	padding: 0 0.3125rem;
	border-radius: 9999px;
	background: var(--ql-subtle);
	font-style: normal;
	font-size: 0.625rem;
	font-weight: 500;
	letter-spacing: 0.02em;
	text-transform: uppercase;
	color: var(--ql-text-muted);
}

.preflight.is-collapsible .preflight__tag {
	background: var(--ql-surface);
}

.preflight__detail {
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	word-break: break-word;
}

/* The container repeats this sentence in its error banner, which is the loud
   copy. Here it is the tail of the diagnosis, so it stays subordinate. */
.preflight__next {
	font-size: 0.6875rem;
	color: var(--ql-danger);
	word-break: break-word;
}

@keyframes preflight-pulse {
	0%,
	100% {
		opacity: 0.35;
		transform: scale(0.75);
	}
	50% {
		opacity: 1;
		transform: scale(1);
	}
}

@media (prefers-reduced-motion: reduce) {
	.preflight__pulse {
		animation-name: none;
		opacity: 1;
	}
}
</style>
