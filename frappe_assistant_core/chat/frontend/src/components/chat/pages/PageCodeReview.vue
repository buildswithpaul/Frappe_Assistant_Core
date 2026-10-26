<template>
	<div class="page-code-review" role="status">
		<div class="page-code-review-bar" :title="tooltip">
			<svg class="page-code-review-icon" viewBox="0 0 24 24" aria-hidden="true">
				<path d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
			</svg>
			<p class="page-code-review-message">
				<span>{{ message }}</span>
				<span v-if="previous" class="page-code-review-note">{{ __("You're seeing the version you last ran.") }}</span>
			</p>
			<div class="page-code-review-buttons">
				<button
					type="button"
					class="page-code-review-toggle"
					:aria-expanded="String(showing)"
					@click="showing = !showing"
				>
					{{ toggleLabel }}
				</button>
				<button type="button" class="page-code-review-run" @click="emit('run')">
					{{ __("Run new version") }}
				</button>
			</div>
		</div>
		<PageCodeDiff v-if="showing" :approved="approved" :script="script" :first="first" />
	</div>
</template>

<script setup>
import { computed, ref } from "vue";

import { __ } from "@/utils/i18n";

import PageCodeDiff from "./PageCodeDiff.vue";

const props = defineProps({
	// "first" before any version of the script was approved, "changed" once FACO changed it.
	state: { type: String, required: true },
	approved: { type: String, default: "" },
	script: { type: String, default: "" },
	// The panel keeps showing the version the user last ran while this one waits.
	previous: { type: Boolean, default: false },
});

const emit = defineEmits(["run"]);

const tooltip = __("Until you run it, Download PDF and FACO's screenshots show the page without this code.");

const showing = ref(false);
const first = computed(() => props.state === "first");
const message = computed(() =>
	first.value
		? __("This page runs code FACO wrote. Check it, then run it.")
		: __("FACO updated this page's code. Check the change, then run the new version."),
);
const toggleLabel = computed(() => {
	if (first.value) return showing.value ? __("Hide code") : __("View code");
	return showing.value ? __("Hide changes") : __("View changes");
});
</script>

<style scoped>
.page-code-review {
	border-bottom: 1px solid var(--ql-border);
	background: var(--ql-accent-soft);
}
.page-code-review-bar {
	display: flex;
	align-items: center;
	flex-wrap: wrap;
	gap: 8px 12px;
	padding: 10px 14px 10px 16px;
}
.page-code-review-icon {
	flex: none;
	width: 18px;
	height: 18px;
	fill: none;
	stroke: var(--ql-accent);
	stroke-width: 1.75;
	stroke-linecap: round;
	stroke-linejoin: round;
}
.page-code-review-message {
	display: flex;
	flex-direction: column;
	gap: 2px;
	flex: 1;
	min-width: 14em;
	margin: 0;
	font-size: 13px;
	line-height: 1.45;
	color: var(--ql-text);
}
.page-code-review-note {
	font-size: 12px;
	color: var(--ql-text-secondary);
}
.page-code-review-buttons {
	display: flex;
	align-items: center;
	gap: 8px;
	flex: none;
}
.page-code-review-toggle,
.page-code-review-run {
	height: 30px;
	padding: 0 12px;
	border-radius: var(--ql-radius-md);
	font-size: 13px;
	font-weight: 500;
	cursor: pointer;
	transition: background-color 0.15s ease, border-color 0.15s ease;
}
.page-code-review-toggle {
	border: 1px solid var(--ql-border);
	background: var(--ql-surface);
	color: var(--ql-text);
}
.page-code-review-toggle:hover {
	border-color: var(--ql-border-hover);
}
.page-code-review-run {
	border: 1px solid var(--ql-accent);
	background: var(--ql-accent);
	/* The surface colour: white on the light accent, ink on dark's brighter one, as New chat does. */
	color: var(--ql-surface);
	font-weight: 600;
}
.page-code-review-run:hover {
	border-color: var(--ql-accent-hover);
	background: var(--ql-accent-hover);
}
.page-code-review-toggle:focus-visible,
.page-code-review-run:focus-visible {
	outline: 2px solid var(--ql-accent);
	outline-offset: 2px;
}

@media (max-width: 767px) {
	.page-code-review-bar {
		padding: 10px 12px;
	}
	.page-code-review-message {
		min-width: calc(100% - 30px);
	}
	.page-code-review-buttons {
		width: 100%;
		justify-content: flex-end;
	}
}
</style>
