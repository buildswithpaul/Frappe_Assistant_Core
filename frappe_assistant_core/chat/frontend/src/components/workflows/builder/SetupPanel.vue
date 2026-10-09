<template>
	<div
		class="setup-panel"
		role="dialog"
		:aria-label="__('Agent setup')"
		@keydown.esc="$emit('close')"
	>
		<header class="setup-header">
			<h2 class="setup-title">{{ __("Setup") }}</h2>
			<button type="button" class="setup-close" :aria-label="__('Close')" @click="$emit('close')">
				×
			</button>
		</header>
		<p v-if="busy" class="setup-busy">{{ __("Checking…") }}</p>
		<ul class="setup-list">
			<li v-for="item in items" :key="item.key" class="setup-item" :class="`state-${item.state}`">
				<span class="setup-mark" aria-hidden="true">{{ MARKS[item.state] }}</span>
				<div class="setup-body">
					<p class="setup-label">{{ item.label }}</p>
					<p class="setup-detail">{{ item.detail }}</p>
					<div class="setup-actions">
						<button
							v-for="action in item.actions"
							:key="action.key"
							type="button"
							class="setup-action"
							@click="$emit('action', action.key)"
						>
							{{ action.label }}
						</button>
					</div>
				</div>
			</li>
		</ul>
	</div>
</template>

<script setup>
import { __ } from "@/utils/i18n";

defineProps({
	items: { type: Array, required: true },
	busy: { type: Boolean, default: false },
});
defineEmits(["action", "close"]);

const MARKS = { ok: "✓", todo: "!", unknown: "?" };
</script>

<style scoped>
.setup-panel {
	position: fixed;
	top: 3.5rem;
	right: 1rem;
	z-index: 1050;
	width: min(24rem, calc(100vw - 2rem));
	padding: var(--ql-space-4);
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-xl);
	box-shadow: 0 12px 32px rgba(0, 0, 0, 0.14);
}
.setup-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	margin-bottom: var(--ql-space-3);
}
.setup-title {
	font-size: 0.9375rem;
	font-weight: 600;
	color: var(--ql-text);
}
.setup-close {
	font-size: 1.25rem;
	color: var(--ql-text-muted);
	background: none;
	border: none;
	cursor: pointer;
}
.setup-busy {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	margin-bottom: var(--ql-space-2);
}
.setup-list {
	display: flex;
	flex-direction: column;
	gap: var(--ql-space-3);
}
.setup-item {
	display: flex;
	gap: var(--ql-space-3);
}
.setup-mark {
	flex-shrink: 0;
	width: 22px;
	height: 22px;
	display: flex;
	align-items: center;
	justify-content: center;
	font-size: 0.75rem;
	font-weight: 700;
	border-radius: 50%;
}
.state-ok .setup-mark {
	color: var(--ql-success);
	background: color-mix(in srgb, var(--ql-success) 14%, transparent);
}
.state-todo .setup-mark {
	color: var(--ql-warning);
	background: color-mix(in srgb, var(--ql-warning) 16%, transparent);
}
.state-unknown .setup-mark {
	color: var(--ql-text-muted);
	background: var(--ql-subtle);
}
.setup-label {
	font-size: 0.8125rem;
	font-weight: 600;
	color: var(--ql-text);
}
.setup-detail {
	font-size: 0.75rem;
	color: var(--ql-text-secondary);
	margin-top: 0.125rem;
	word-break: break-word;
}
.setup-actions {
	display: flex;
	gap: var(--ql-space-2);
	margin-top: var(--ql-space-1);
}
.setup-action {
	font-size: 0.75rem;
	color: var(--ql-accent);
	background: none;
	border: none;
	padding: 0;
	cursor: pointer;
}
.setup-action:hover {
	text-decoration: underline;
}
</style>
