<template>
	<!-- Without a dock beside the chat (the Desk widget), the page opens in Desk instead. -->
	<component
		:is="dockMounted ? 'button' : 'a'"
		v-bind="dockMounted ? { type: 'button' } : { href: deskUrl }"
		class="fac-page-chip"
		:aria-label="__('Open {0}', [chip.title])"
		@click="dockMounted && open(chip.name)"
	>
		<span class="fac-page-chip-icon" aria-hidden="true">▤</span>
		<span class="fac-page-chip-title">{{ chip.title }}</span>
		<span class="fac-page-chip-version">v{{ chip.version }}</span>
		<span v-if="chip.pending" class="fac-page-chip-pending">{{ __("Updating…") }}</span>
	</component>
</template>

<script setup>
import { computed } from "vue";

import { usePagePanel } from "@/composables/usePagePanel";
import { __ } from "@/utils/i18n";

const props = defineProps({
	// {name, title, version, pending}, from derivePageChips.
	chip: { type: Object, required: true },
});

const { open, dockMounted } = usePagePanel();
const deskUrl = computed(() => `/app/fac-pages/${encodeURIComponent(props.chip.name)}`);
</script>

<style scoped>
.fac-page-chip {
	display: inline-flex;
	align-items: center;
	gap: 8px;
	max-width: 100%;
	padding: 6px 12px;
	border: 1px solid var(--ql-border);
	border-radius: 999px;
	background: var(--ql-surface);
	color: var(--ql-text);
	font-size: 13px;
	text-decoration: none;
	cursor: pointer;
}
.fac-page-chip:hover {
	border-color: var(--ql-border-hover);
	background: var(--ql-subtle);
}
.fac-page-chip-icon {
	color: var(--ql-accent);
}
.fac-page-chip-title {
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
	font-weight: 500;
}
.fac-page-chip-version,
.fac-page-chip-pending {
	flex: none;
	color: var(--ql-text-muted);
	font-family: var(--ql-font-mono);
	font-size: 11px;
}
</style>
