<template>
	<div class="expandable-artifact">
		<slot />
		<button
			v-if="canExpand"
			type="button"
			class="expand-btn"
			data-test="expand-btn"
			aria-label="Expand"
			@click="open = true"
		>
			<svg class="expand-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"
				/>
			</svg>
		</button>

		<ArtifactModal
			v-if="open"
			:capture="capture"
			:to-png="toPng"
			:title="title"
			@close="open = false"
		/>
	</div>
</template>

<script setup>
import { ref, computed, defineAsyncComponent } from "vue";

// Lazy: the modal pulls in the zoom composable + heavy artifact handling and is
// only needed once a user expands. A dynamic import also lets unit tests stub
// ArtifactModal (Vite does not eagerly resolve dynamic imports the way it does
// static ones). Mirrors the registry's defineAsyncComponent pattern for charts.
const ArtifactModal = defineAsyncComponent(() => import("./ArtifactModal.vue"));

const props = defineProps({
	// () => { node: HTMLElement, cleanup: () => void } | null — called ONLY by
	// the modal on open. Must NOT be called for visibility checks (it may
	// allocate, e.g. a live ECharts instance).
	capture: { type: Function, required: true },
	// () => boolean — cheap, allocation-free predicate: is there an artifact to
	// expand right now? Used for the expand-button visibility so we never invoke
	// the heavy capture() factory on every render. Defaults to always-true.
	canCapture: { type: Function, default: () => true },
	// () => Promise<string>  (PNG dataURL)
	toPng: { type: Function, required: true },
	title: { type: String, default: "artifact" },
	disabled: { type: Boolean, default: false },
});

const open = ref(false);

// Hide the affordance while streaming (disabled) or when there is no artifact
// to expand. Uses the cheap canCapture() predicate — never the heavy capture()
// factory — so visibility checks don't allocate or have side effects.
const canExpand = computed(() => {
	if (props.disabled) return false;
	try {
		return props.canCapture() !== false;
	} catch {
		return false;
	}
});
</script>

<style scoped>
.expandable-artifact {
	position: relative;
}

.expand-btn {
	position: absolute;
	top: 0.5rem;
	right: 0.5rem;
	display: flex;
	align-items: center;
	justify-content: center;
	width: 1.75rem;
	height: 1.75rem;
	padding: 0;
	color: var(--ql-text-muted);
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	cursor: pointer;
	opacity: 0;
	transition: opacity 0.15s ease, color 0.15s ease, border-color 0.15s ease;
}

.expandable-artifact:hover .expand-btn,
.expand-btn:focus-visible {
	opacity: 1;
}

/* Always visible on touch (no hover) */
@media (hover: none) {
	.expand-btn {
		opacity: 1;
	}
}

.expand-btn:hover {
	color: var(--ql-accent);
	border-color: var(--ql-accent);
}

.expand-icon {
	width: 1rem;
	height: 1rem;
}
</style>
