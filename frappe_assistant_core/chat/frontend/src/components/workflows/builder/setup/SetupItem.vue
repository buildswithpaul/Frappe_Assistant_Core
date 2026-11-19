<template>
	<li class="setup-item" :class="`state-${item.state}`" :data-test="`setup-${item.key}`">
		<span class="setup-mark" aria-hidden="true">{{ MARKS[item.state] }}</span>
		<div class="setup-body">
			<p class="setup-label">
				{{ item.label }}
				<span v-if="!item.required && item.key !== 'model'" class="setup-optional">{{
					__("optional")
				}}</span>
			</p>
			<p v-if="showDetail" class="setup-detail">{{ item.detail }}</p>
			<slot />
		</div>
	</li>
</template>

<script setup>
import { __ } from "@/utils/i18n";

defineProps({
	item: { type: Object, required: true },
	showDetail: { type: Boolean, default: true },
});

const MARKS = { ok: "✓", todo: "!", unknown: "?" };
</script>

<style scoped>
.setup-item {
	display: flex;
	gap: var(--ql-space-3);
	padding: var(--ql-space-3) 0;
	border-bottom: 1px solid var(--ql-border);
}
.setup-item:last-child {
	border-bottom: none;
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
.setup-body {
	flex: 1;
	min-width: 0;
}
.setup-label {
	font-size: 0.8125rem;
	font-weight: 600;
	color: var(--ql-text);
}
.setup-optional {
	margin-left: 0.25rem;
	font-size: 0.6875rem;
	font-weight: 400;
	color: var(--ql-text-muted);
}
.setup-detail {
	font-size: 0.75rem;
	color: var(--ql-text-secondary);
	margin-top: 0.125rem;
	word-break: break-word;
}
</style>
