<template>
	<button type="button" class="page-card" :class="`page-card--${kind}`" @click="emit('open', page.name)">
		<span class="page-card-preview" aria-hidden="true">
			<span v-for="(height, i) in bars" :key="i" class="page-card-bar" :style="{ height: `${height}%` }" />
		</span>
		<span class="page-card-body">
			<span class="page-card-title">{{ page.title || page.name }}</span>
			<span class="page-card-context-row">
				<span v-if="kind === 'draft'" class="page-card-chip">{{ __("Draft") }}</span>
				<span class="page-card-context">{{ context }}</span>
			</span>
			<span class="page-card-updated">{{ updatedAgo }}</span>
		</span>
	</button>
</template>

<script setup>
import { computed } from "vue";

import { formatRelativeTime } from "@/composables/useFormatters";
import { __ } from "@/utils/i18n";

const props = defineProps({
	page: { type: Object, required: true },
});

const emit = defineEmits(["open"]);

const BAR_COUNT = 5;
const MIN_BAR = 25;
const MAX_ROLES_SHOWN = 2;

const kind = computed(() => {
	if (props.page.draft) return "draft";
	return props.page.visibility === "Shared" ? "shared" : "personal";
});

// A small string hash seeds each bar, so the same page always draws the same preview.
const bars = computed(() => {
	let seed = 0;
	for (const char of props.page.name) seed = (seed * 31 + char.charCodeAt(0)) >>> 0;
	return Array.from({ length: BAR_COUNT }, () => {
		seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
		return MIN_BAR + (seed % (100 - MIN_BAR));
	});
});

// The helper opens with a capital ("Just now"), which reads wrong after "Updated".
const updatedAgo = computed(() => {
	const text = formatRelativeTime(props.page.modified);
	return __("Updated {0}", [text.charAt(0).toLowerCase() + text.slice(1)]);
});

const rolesText = computed(() => {
	const roles = props.page.roles || [];
	const shown = roles.slice(0, MAX_ROLES_SHOWN).join(", ");
	const more = roles.length - MAX_ROLES_SHOWN;
	return more > 0 ? `${shown} +${more}` : shown;
});

const context = computed(() => {
	if (kind.value === "draft") return __("Not published yet · only admins see it");
	if (kind.value === "personal") return __("Only you");
	return rolesText.value ? __("Shared with {0}", [rolesText.value]) : __("Shared");
});
</script>

<style scoped>
.page-card {
	display: flex;
	flex-direction: column;
	width: 100%;
	padding: 0;
	overflow: hidden;
	text-align: left;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	color: var(--ql-text);
	cursor: pointer;
	transition:
		border-color 0.15s ease,
		box-shadow 0.15s ease;
}

.page-card:hover {
	border-color: var(--ql-border-hover);
	box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.page-card:focus-visible {
	outline: none;
	border-color: var(--ql-accent);
	box-shadow: 0 0 0 3px var(--ql-accent-soft);
}

.page-card-preview {
	display: flex;
	align-items: flex-end;
	gap: 0.5rem;
	height: 120px;
	padding: 1rem;
	background: var(--ql-subtle);
	border-bottom: 1px solid var(--ql-border);
}

.page-card-bar {
	flex: 1;
	border-radius: 0.25rem 0.25rem 0 0;
	background: var(--page-card-tint);
}

.page-card--personal {
	--page-card-tint: color-mix(in srgb, var(--ql-accent) 22%, transparent);
}

.page-card--shared {
	--page-card-tint: color-mix(in srgb, var(--ql-accent) 50%, transparent);
}

.page-card--draft {
	--page-card-tint: color-mix(in srgb, var(--ql-warning) 45%, transparent);
}

.page-card-body {
	display: flex;
	flex-direction: column;
	gap: 0.375rem;
	padding: 0.875rem 1rem 1rem;
}

.page-card-title {
	font-size: 0.9375rem;
	font-weight: 500;
	display: -webkit-box;
	-webkit-line-clamp: 2;
	line-clamp: 2;
	-webkit-box-orient: vertical;
	overflow: hidden;
}

.page-card-context-row {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	min-width: 0;
}

.page-card-context,
.page-card-updated {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.page-card-chip {
	flex-shrink: 0;
	font-size: 0.7rem;
	padding: 0.125rem 0.5rem;
	border-radius: 999px;
	background: color-mix(in srgb, var(--ql-warning) 18%, transparent);
	color: var(--ql-warning);
}
</style>
