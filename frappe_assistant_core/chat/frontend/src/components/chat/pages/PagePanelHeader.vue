<template>
	<header class="page-panel-header">
		<button type="button" class="page-panel-icon page-panel-back" :aria-label="__('Back to chat')" @click="emit('close')">
			<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 19l-7-7 7-7" /></svg>
		</button>
		<div class="page-panel-heading">
			<h2 class="page-panel-title" :title="title">{{ title }}</h2>
			<span v-if="version" class="page-panel-version">v{{ version }}</span>
			<span v-if="pending" class="page-panel-updating" role="status">{{ __("Updating…") }}</span>
		</div>
		<div class="page-panel-actions">
			<PageListMenu />
			<a
				class="page-panel-icon page-panel-fullscreen"
				:href="deskUrl"
				target="_blank"
				rel="noopener"
				:aria-label="__('Open full screen in Desk')"
				:title="__('Full screen')"
			>
				<svg viewBox="0 0 24 24" aria-hidden="true">
					<path d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
				</svg>
			</a>
			<button
				v-if="shareable"
				type="button"
				class="page-panel-icon page-panel-share"
				:aria-label="__('Share with your team')"
				:title="__('Share')"
				@click="emit('share')"
			>
				<svg viewBox="0 0 24 24" aria-hidden="true">
					<path
						d="M8.7 13.3a3 3 0 010-2.6m0 2.6a3 3 0 110-2.6m0 2.6l6.6 3.4m-6.6-6l6.6-3.4m0 0a3 3 0 105.4-2.6 3 3 0 00-5.4 2.6zm0 9.4a3 3 0 105.4 2.6 3 3 0 00-5.4-2.6z"
					/>
				</svg>
			</button>
			<button type="button" class="page-panel-pdf" :disabled="pdfDisabled" @click="emit('pdf')">
				<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>
				<span class="page-panel-pdf-label">{{ __("Download PDF") }}</span>
			</button>
			<button type="button" class="page-panel-icon page-panel-close" :aria-label="__('Close page')" :title="__('Close')" @click="emit('close')">
				<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 18L18 6M6 6l12 12" /></svg>
			</button>
		</div>
	</header>
</template>

<script setup>
import { __ } from "@/utils/i18n";

import PageListMenu from "./PageListMenu.vue";

defineProps({
	title: { type: String, default: "" },
	version: { type: Number, default: 0 },
	pending: { type: Boolean, default: false },
	shareable: { type: Boolean, default: false },
	deskUrl: { type: String, required: true },
	pdfDisabled: { type: Boolean, default: false },
});

const emit = defineEmits(["close", "share", "pdf"]);
</script>

<style scoped>
.page-panel-header {
	display: flex;
	align-items: center;
	gap: 12px;
	min-height: 52px;
	padding: 8px 10px 8px 16px;
	border-bottom: 1px solid var(--ql-border);
	background: var(--ql-surface);
}
.page-panel-heading {
	display: flex;
	align-items: baseline;
	gap: 8px;
	flex: 1;
	min-width: 0;
}
.page-panel-title {
	margin: 0;
	min-width: 0;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
	font-size: 15px;
	font-weight: 600;
	color: var(--ql-text);
}
.page-panel-version,
.page-panel-updating {
	flex: none;
	font-size: 12px;
	font-variant-numeric: tabular-nums;
	color: var(--ql-text-muted);
}
.page-panel-actions {
	display: flex;
	align-items: center;
	gap: 2px;
	flex: none;
}
/* Icon controls, as the top bar draws them: quiet until hovered, labelled for screen readers. */
.page-panel-icon {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	gap: 2px;
	height: 32px;
	min-width: 32px;
	padding: 0 6px;
	border: none;
	border-radius: var(--ql-radius-sm);
	background: none;
	color: var(--ql-text-secondary);
	cursor: pointer;
	transition: background-color 0.15s ease, color 0.15s ease;
}
.page-panel-icon:hover {
	background: var(--ql-subtle);
	color: var(--ql-text);
}
.page-panel-icon svg,
.page-panel-pdf svg {
	width: 18px;
	height: 18px;
	fill: none;
	stroke: currentColor;
	stroke-width: 1.75;
	stroke-linecap: round;
	stroke-linejoin: round;
}
.page-panel-pdf {
	display: inline-flex;
	align-items: center;
	gap: 6px;
	height: 32px;
	margin: 0 4px 0 6px;
	padding: 0 12px 0 10px;
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-md);
	background: var(--ql-surface);
	color: var(--ql-text);
	font-size: 13px;
	font-weight: 500;
	cursor: pointer;
	transition: background-color 0.15s ease, border-color 0.15s ease;
}
.page-panel-pdf:hover:not(:disabled) {
	border-color: var(--ql-border-hover);
	background: var(--ql-subtle);
}
.page-panel-pdf:disabled {
	opacity: 0.5;
	cursor: default;
}
.page-panel-icon:focus-visible,
.page-panel-pdf:focus-visible {
	outline: 2px solid var(--ql-accent);
	outline-offset: 1px;
}
.page-panel-back {
	display: none;
}

/* Below 768 the panel covers the chat: a back control replaces close, and Download PDF keeps
   only its icon so the title keeps the room. */
@media (max-width: 767px) {
	.page-panel-header {
		gap: 4px;
		padding: 6px 6px 6px 4px;
	}
	.page-panel-back {
		display: inline-flex;
	}
	.page-panel-close {
		display: none;
	}
	.page-panel-pdf {
		width: 32px;
		margin: 0;
		padding: 0;
		justify-content: center;
		border-color: transparent;
	}
	.page-panel-pdf-label {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip-path: inset(50%);
		white-space: nowrap;
	}
}
</style>
