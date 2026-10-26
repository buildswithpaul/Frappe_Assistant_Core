<template>
	<div ref="root" class="page-list-menu" @keydown.esc="isOpen = false">
		<button
			type="button"
			class="page-panel-mine"
			aria-haspopup="menu"
			:aria-expanded="isOpen"
			:aria-label="__('My pages')"
			:title="__('My pages')"
			@click="toggle"
		>
			<svg viewBox="0 0 24 24" aria-hidden="true">
				<path d="M8 4h9a2 2 0 012 2v11M5 8h9a1 1 0 011 1v10a1 1 0 01-1 1H5a1 1 0 01-1-1V9a1 1 0 011-1z" />
			</svg>
			<svg class="page-panel-mine-chevron" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 10l5 5 5-5" /></svg>
		</button>
		<div v-if="isOpen" class="page-list-menu-popover" role="menu">
			<p v-if="loading" class="page-list-menu-message">{{ __("Loading…") }}</p>
			<p v-else-if="failed" class="page-list-menu-message">{{ __("Your pages could not be listed.") }}</p>
			<p v-else-if="!pages.length" class="page-list-menu-message">{{ __("No pages yet.") }}</p>
			<button
				v-for="item in pages"
				v-else
				:key="item.name"
				type="button"
				role="menuitem"
				class="page-panel-mine-item"
				@click="choose(item.name)"
			>
				{{ item.title || item.name }}
			</button>
		</div>
	</div>
</template>

<script setup>
import { onBeforeUnmount, ref } from "vue";

import { facPage } from "@/api/domains/facPage";
import { usePagePanel } from "@/composables/usePagePanel";
import { __ } from "@/utils/i18n";
import { logger } from "@/utils/logger";

const { open } = usePagePanel();

const isOpen = ref(false);
const loading = ref(false);
const failed = ref(false);
const pages = ref([]);
const root = ref(null);

// A press anywhere else closes the menu, as the app's other menus do.
function onOutside(event) {
	if (isOpen.value && !root.value?.contains(event.target)) isOpen.value = false;
}
document.addEventListener("pointerdown", onOutside);
onBeforeUnmount(() => document.removeEventListener("pointerdown", onOutside));

// Listed on each open, so a page FACO just made is there.
async function toggle() {
	isOpen.value = !isOpen.value;
	if (!isOpen.value) return;
	loading.value = true;
	failed.value = false;
	try {
		pages.value = (await facPage.listMine()) || [];
	} catch (error) {
		logger.error("FAC Pages could not be listed", error);
		failed.value = true;
	} finally {
		loading.value = false;
	}
}

function choose(name) {
	isOpen.value = false;
	open(name);
}
</script>

<style scoped>
.page-list-menu {
	position: relative;
}
.page-panel-mine {
	display: inline-flex;
	align-items: center;
	height: 32px;
	padding: 0 4px 0 7px;
	border: none;
	border-radius: var(--ql-radius-sm);
	background: none;
	color: var(--ql-text-secondary);
	cursor: pointer;
	transition: background-color 0.15s ease, color 0.15s ease;
}
.page-panel-mine:hover,
.page-panel-mine[aria-expanded="true"] {
	background: var(--ql-subtle);
	color: var(--ql-text);
}
.page-panel-mine:focus-visible {
	outline: 2px solid var(--ql-accent);
	outline-offset: 1px;
}
.page-panel-mine svg {
	width: 18px;
	height: 18px;
	fill: none;
	stroke: currentColor;
	stroke-width: 1.75;
	stroke-linecap: round;
	stroke-linejoin: round;
}
.page-panel-mine .page-panel-mine-chevron {
	width: 14px;
	height: 14px;
}
.page-list-menu-popover {
	position: absolute;
	top: calc(100% + 4px);
	right: 0;
	z-index: 10;
	display: flex;
	flex-direction: column;
	min-width: 220px;
	max-height: 320px;
	overflow-y: auto;
	padding: 4px;
	border: 1px solid var(--ql-border);
	border-radius: 8px;
	background: var(--ql-surface);
	box-shadow: 0 8px 24px rgb(0 0 0 / 0.12);
}
.page-panel-mine-item {
	padding: 7px 10px;
	border: none;
	border-radius: 6px;
	background: none;
	color: var(--ql-text);
	font-size: 13px;
	text-align: left;
	cursor: pointer;
}
.page-panel-mine-item:hover {
	background: var(--ql-subtle);
}
.page-list-menu-message {
	margin: 0;
	padding: 7px 10px;
	font-size: 13px;
	color: var(--ql-text-muted);
}
</style>
