<template>
	<button type="button" class="fac-page-chip" :aria-label="__('Open {0}', [chip.title])" @click="open(chip.name)">
		<span class="fac-page-chip-icon" aria-hidden="true">▤</span>
		<span class="fac-page-chip-title">{{ chip.title }}</span>
		<span class="fac-page-chip-version">v{{ chip.version }}</span>
		<span v-if="chip.pending" class="fac-page-chip-pending">{{ __("Updating…") }}</span>
	</button>
</template>

<script setup>
import { usePagePanel } from "@/composables/usePagePanel";
import { __ } from "@/utils/i18n";

defineProps({
	// {name, title, version, pending}, from derivePageChips.
	chip: { type: Object, required: true },
});

const { open } = usePagePanel();
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
