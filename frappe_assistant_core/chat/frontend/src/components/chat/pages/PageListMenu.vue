<template>
	<div class="page-list-menu">
		<button
			type="button"
			class="page-panel-mine"
			aria-haspopup="menu"
			:aria-expanded="isOpen"
			@click="toggle"
		>
			{{ __("My pages") }} ▾
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
import { ref } from "vue";

import { facPage } from "@/api/domains/facPage";
import { usePagePanel } from "@/composables/usePagePanel";
import { __ } from "@/utils/i18n";
import { logger } from "@/utils/logger";

const { open } = usePagePanel();

const isOpen = ref(false);
const loading = ref(false);
const failed = ref(false);
const pages = ref([]);

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
	padding: 5px 9px;
	border: none;
	border-radius: 6px;
	background: none;
	color: var(--ql-text-secondary);
	font-size: 13px;
	cursor: pointer;
}
.page-panel-mine:hover {
	background: var(--ql-subtle);
	color: var(--ql-text);
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
