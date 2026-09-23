<template>
	<div class="wizard-shell" data-test="connect-wizard" @click.self="$emit('close')">
		<div class="wizard-shell__panel" role="dialog" aria-modal="true" :aria-label="eyebrow">
			<header class="wizard-shell__header">
				<p class="wizard-shell__eyebrow">{{ eyebrow }}</p>
				<button
					type="button"
					class="wizard-shell__close"
					data-test="close"
					aria-label="Close"
					@click="$emit('close')"
				>
					<svg viewBox="0 0 14 14" class="wizard-shell__close-glyph" aria-hidden="true">
						<path d="M3.6 3.6 10.4 10.4M10.4 3.6 3.6 10.4" />
					</svg>
				</button>
			</header>

			<div class="wizard-shell__body">
				<slot />

				<p v-if="error" class="wizard-shell__error" role="alert" data-test="error">
					<svg viewBox="0 0 14 14" class="wizard-shell__error-glyph" aria-hidden="true">
						<path d="M7 2 13 12.4H1zM7 6v2.5M7 10.3v.1" />
					</svg>
					<span>{{ error }}</span>
				</p>

				<slot name="footer" />
			</div>
		</div>
	</div>
</template>

<script setup>
// The panel furniture every step shares: the overlay, the dialog, the flow
// label, the close control, and the one error slot the container writes to.
defineProps({
	eyebrow: { type: String, default: "" },
	error: { type: String, default: "" },
});

defineEmits(["close"]);
</script>

<style scoped>
.wizard-shell {
	position: fixed;
	inset: 0;
	display: flex;
	align-items: center;
	justify-content: center;
	padding: var(--ql-space-4);
	background: rgba(0, 0, 0, 0.45);
	backdrop-filter: blur(2px);
	z-index: 1200;
}

.wizard-shell__panel {
	display: flex;
	flex-direction: column;
	width: 100%;
	max-width: 30rem;
	max-height: 85vh;
	overflow: hidden;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-xl);
	box-shadow:
		0 24px 48px -16px rgba(0, 0, 0, 0.35),
		0 4px 12px -6px rgba(0, 0, 0, 0.14);
}

.wizard-shell__header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: var(--ql-space-3);
	flex: none;
	padding: var(--ql-space-3) var(--ql-space-3) var(--ql-space-3) var(--ql-space-6);
	border-bottom: 1px solid var(--ql-border);
	background: var(--ql-subtle);
}

.wizard-shell__eyebrow {
	min-width: 0;
	margin: 0;
	overflow: hidden;
	font-size: 0.6875rem;
	font-weight: 600;
	letter-spacing: 0.08em;
	text-transform: uppercase;
	text-overflow: ellipsis;
	white-space: nowrap;
	color: var(--ql-text-muted);
}

.wizard-shell__close {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	flex: none;
	width: 1.75rem;
	height: 1.75rem;
	padding: 0;
	background: none;
	border: none;
	border-radius: var(--ql-radius-sm);
	color: var(--ql-text-muted);
	cursor: pointer;
}

.wizard-shell__close:hover {
	background: var(--ql-surface);
	color: var(--ql-text);
}

.wizard-shell__close-glyph {
	width: 0.75rem;
	height: 0.75rem;
	fill: none;
	stroke: currentColor;
	stroke-width: 1.6;
	stroke-linecap: round;
}

.wizard-shell__body {
	display: flex;
	flex-direction: column;
	gap: var(--ql-space-4);
	flex: 1;
	min-height: 0;
	padding: var(--ql-space-6);
	overflow-y: auto;
}

.wizard-shell__error {
	display: flex;
	align-items: flex-start;
	gap: 0.5rem;
	margin: 0;
	padding: 0.625rem 0.75rem;
	border-radius: var(--ql-radius-md);
	border-left: 3px solid var(--ql-danger);
	background: color-mix(in srgb, var(--ql-danger) 8%, transparent);
	font-size: 0.8125rem;
	line-height: 1.5;
	text-wrap: pretty;
	color: var(--ql-text);
}

.wizard-shell__error-glyph {
	flex: none;
	width: 0.875rem;
	height: 0.875rem;
	margin-top: 0.1875rem;
	fill: none;
	stroke: var(--ql-danger);
	stroke-width: 1.4;
	stroke-linecap: round;
	stroke-linejoin: round;
}
</style>
