<template>
	<div class="input-toolbar">
		<!-- Left cluster: attach + mic + markdown toggle + context chip -->
		<div class="toolbar-left">
			<button
				@click="$emit('toggle-plus')"
				data-composer-plus-trigger
				class="toolbar-btn toolbar-btn-plus"
				:class="{ 'toolbar-btn-active': plusOpen }"
				:disabled="isStreaming"
				:aria-pressed="plusOpen"
				aria-label="Attach or toggle composer modes"
				title="Attach a file, Web search, Thinking"
			>
				<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 5v14M5 12h14" />
				</svg>
			</button>

			<button
				v-if="webSearchAvailable"
				@click="$emit('toggle-web-search')"
				class="toolbar-btn toolbar-btn-pill"
				:class="{ 'toolbar-btn-active': webSearch }"
				:disabled="isStreaming"
				:aria-pressed="webSearch"
				aria-label="Toggle web search"
				title="Web search"
			>
				<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
						d="M21 12a9 9 0 11-18 0 9 9 0 0118 0zM3.6 9h16.8M3.6 15h16.8M12 3a15 15 0 010 18a15 15 0 010-18z" />
				</svg>
				<span class="pill-label">Web search</span>
			</button>

			<button
				@click="$emit('toggle-thinking')"
				class="toolbar-btn toolbar-btn-pill"
				:class="{ 'toolbar-btn-active': thinking }"
				:disabled="isStreaming"
				:aria-pressed="thinking"
				aria-label="Toggle thinking"
				title="Thinking"
			>
				<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
						d="M12 3l1.9 4.6L18.5 9l-4.6 1.9L12 15.5l-1.9-4.6L5.5 9l4.6-1.4L12 3z" />
				</svg>
				<span class="pill-label">Thinking</span>
			</button>

			<MicButton
				@transcribed="$emit('transcribed', $event)"
				@error="$emit('voice-error', $event)"
			/>

			<button
				v-if="hasMarkdown"
				@click="$emit('toggle-markdown')"
				class="toolbar-btn"
				:class="{ 'toolbar-btn-active': showMarkdownPreview }"
				:aria-pressed="showMarkdownPreview"
				aria-label="Toggle markdown preview"
				title="Toggle markdown preview"
			>
				<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
					/>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
					/>
				</svg>
			</button>

			<div
				v-if="context"
				class="context-chip"
				:title="`${context.type}: ${context.doctype || context.name}`"
			>
				<svg class="context-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
					/>
				</svg>
				<span class="context-text">{{ context.doctype || context.name }}</span>
			</div>
		</div>

		<!-- Right cluster: hint + send/stop -->
		<div class="toolbar-right">
			<span class="kbd-hint" aria-hidden="true">
				<kbd>⏎</kbd> send
				<span class="kbd-sep">·</span>
				<kbd>⇧⏎</kbd> new line
			</span>

			<button
				v-if="isStreaming"
				@click="$emit('stop')"
				class="send-btn send-btn-stop"
				title="Stop generating"
				aria-label="Stop generating"
			>
				<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<rect x="7" y="7" width="10" height="10" rx="1.5" fill="currentColor" stroke="none" />
				</svg>
			</button>
			<button
				v-else
				@click="$emit('send')"
				:disabled="!canSend"
				class="send-btn"
				:class="{ 'send-btn-enabled': canSend }"
				aria-label="Send message"
			>
				<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M5 12l14-7-4 18-3-8-7-3z"
					/>
				</svg>
			</button>
		</div>
	</div>
</template>

<script setup>
import MicButton from "@/components/chat/MicButton.vue";

defineProps({
	isStreaming: { type: Boolean, default: false },
	canSend: { type: Boolean, default: false },
	hasMarkdown: { type: Boolean, default: false },
	showMarkdownPreview: { type: Boolean, default: false },
	context: { type: Object, default: null },
	plusOpen: { type: Boolean, default: false },
	webSearch: { type: Boolean, default: false },
	thinking: { type: Boolean, default: false },
	webSearchAvailable: { type: Boolean, default: false },
});

defineEmits([
	"toggle-plus",
	"toggle-web-search",
	"toggle-thinking",
	"transcribed",
	"voice-error",
	"toggle-markdown",
	"send",
	"stop",
]);
</script>

<style scoped>
.input-toolbar {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 0.5rem;
	padding: 0.375rem 0.625rem 0.5rem;
	min-height: 2.5rem;
}

.toolbar-left,
.toolbar-right {
	display: flex;
	align-items: center;
	gap: 0.375rem;
	min-width: 0;
}

.toolbar-left {
	flex: 1;
	min-width: 0;
}

.toolbar-btn {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	width: 2rem;
	height: 2rem;
	background: transparent;
	border: none;
	border-radius: 0.5rem;
	color: var(--ql-text-muted);
	cursor: pointer;
	transition: all 0.15s ease;
	flex-shrink: 0;
}

.toolbar-btn:hover:not(:disabled) {
	color: var(--ql-text);
	background: var(--ql-subtle);
}

.toolbar-btn:disabled {
	opacity: 0.4;
	cursor: not-allowed;
}

.toolbar-btn-active {
	color: var(--ql-accent);
	background: var(--ql-accent-soft);
}

.toolbar-btn svg {
	width: 1.125rem;
	height: 1.125rem;
}

.toolbar-btn-plus svg {
	width: 1.25rem;
	height: 1.25rem;
}

.toolbar-btn-pill {
	width: auto;
	gap: 0.375rem;
	padding: 0 0.625rem;
	flex-shrink: 0;
}

.pill-label {
	font-size: 0.75rem;
	font-weight: 500;
	white-space: nowrap;
}

.context-chip {
	display: inline-flex;
	align-items: center;
	gap: 0.375rem;
	padding: 0.25rem 0.5rem;
	background: var(--ql-subtle);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	font-size: 0.75rem;
	color: var(--ql-text);
	min-width: 0;
	flex-shrink: 1;
}

.context-icon {
	width: 0.75rem;
	height: 0.75rem;
	color: var(--ql-text-muted);
	flex-shrink: 0;
}

.context-text {
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
	max-width: 200px;
}

.kbd-hint {
	display: inline-flex;
	align-items: center;
	gap: 0.25rem;
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	white-space: nowrap;
	opacity: 0;
	transition: opacity 0.2s ease;
	pointer-events: none;
}

.kbd-hint kbd {
	display: inline-block;
	padding: 0.0625rem 0.25rem;
	font-family: inherit;
	font-size: 0.6875rem;
	color: var(--ql-text);
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.25rem;
	line-height: 1;
}

.kbd-sep {
	color: var(--ql-border);
	margin: 0 0.125rem;
}

.send-btn {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	width: 2rem;
	height: 2rem;
	border: none;
	border-radius: 9999px;
	background: var(--ql-border);
	color: var(--ql-text-muted);
	cursor: not-allowed;
	transition: all 0.15s ease;
	flex-shrink: 0;
}

.send-btn svg {
	width: 1rem;
	height: 1rem;
}

.send-btn-enabled {
	background: var(--ql-accent);
	color: #fff;
	cursor: pointer;
}

.send-btn-enabled:hover {
	background: var(--ql-accent-hover);
}

.send-btn-enabled:active {
	transform: scale(0.94);
}

.send-btn-stop {
	background: var(--ql-danger);
	color: #fff;
	cursor: pointer;
}

.send-btn-stop:hover {
	filter: brightness(1.08);
}

@media (max-width: 640px) {
	.kbd-hint {
		display: none;
	}
	.context-text {
		max-width: 120px;
	}
	.pill-label {
		display: none;
	}
	.toolbar-btn-pill {
		width: 2rem;
		padding: 0;
		justify-content: center;
	}
}
</style>
