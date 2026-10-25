<template>
	<section class="page-panel" :aria-label="title || __('Page')">
		<header class="page-panel-header">
			<button type="button" class="page-panel-back" :aria-label="__('Back to chat')" @click="close">
				← {{ __("Chat") }}
			</button>
			<div class="page-panel-heading">
				<h2 class="page-panel-title">{{ title }}</h2>
				<span class="page-panel-version">v{{ version }}</span>
				<span v-if="pending" class="page-panel-updating">{{ __("Updating…") }}</span>
			</div>
			<div class="page-panel-actions">
				<PageListMenu />
				<a class="page-panel-action page-panel-fullscreen" :href="deskUrl" target="_blank" rel="noopener">
					{{ __("Full screen") }}
				</a>
				<button v-if="shareable" type="button" class="page-panel-action page-panel-share" @click="share">
					{{ __("Share…") }}
				</button>
				<button type="button" class="page-panel-action page-panel-pdf" :disabled="!page" @click="downloadPdf">
					{{ __("Download PDF") }}
				</button>
				<button type="button" class="page-panel-close" :aria-label="__('Close page')" @click="close">×</button>
			</div>
		</header>

		<p v-if="shareNote" class="page-panel-note" role="status">{{ shareNote }}</p>
		<p v-if="unsupported || scriptFailed" class="page-panel-note" role="status">
			{{
				unsupported
					? __("This page uses parts of Desk the chat can't run.")
					: __("Part of this page didn't load.")
			}}
			<a class="page-panel-open-desk" :href="deskUrl" target="_blank" rel="noopener">{{ __("Open in Desk") }}</a>
		</p>

		<div class="page-panel-body">
			<p v-if="loadFailed" class="page-panel-message">{{ __("This page could not be shown.") }}</p>
			<p v-else-if="!page" class="page-panel-message">{{ __("Loading…") }}</p>
			<PageView
				v-else
				ref="view"
				:key="renderKey"
				:page="page"
				:user="user"
				@unsupported="unsupported = $event"
				@error="onScriptError"
			/>
		</div>
	</section>
</template>

<script setup>
import { computed, ref, watch } from "vue";

import { facPage } from "@/api/domains/facPage";
import { usePagePanel } from "@/composables/usePagePanel";
import { __ } from "@/utils/i18n";
import { logger } from "@/utils/logger";
import { printPage } from "@/utils/pagePrint";

import PageListMenu from "./PageListMenu.vue";
import PageView from "./PageView.vue";

const props = defineProps({
	// The FAC Page record name; a personal page's name is not its slug.
	name: { type: String, required: true },
	version: { type: Number, default: 0 },
	pending: { type: Boolean, default: false },
	// System Managers ask FACO to share; sharing goes through its approval card.
	canShare: { type: Boolean, default: false },
	user: { type: String, default: "" },
	refreshKey: { type: Number, default: 0 },
});

const emit = defineEmits(["share"]);

const { close } = usePagePanel();

const page = ref(null);
const loadFailed = ref(false);
const unsupported = ref(null);
const scriptFailed = ref(false);
const shareNote = ref("");
const renderKey = ref(0);
const view = ref(null);
let request = 0;

const title = computed(() => page.value?.title || props.name);
// Sharing is for the owner's personal page; a Shared page already is.
const shareable = computed(
	() => Boolean(page.value) && page.value.visibility !== "Shared" && page.value.owner_is_me !== false,
);
const deskUrl = computed(() => `/app/fac-pages/${encodeURIComponent(props.name)}`);

async function load() {
	const current = ++request;
	loadFailed.value = false;
	unsupported.value = null;
	scriptFailed.value = false;
	try {
		const data = await facPage.getPage(props.name);
		if (current !== request) return;
		if (!data || typeof data !== "object") throw new Error("get_page returned no page");
		page.value = data;
		renderKey.value++;
	} catch (error) {
		if (current !== request) return;
		logger.error("FAC Page could not be loaded", error);
		page.value = null;
		loadFailed.value = true;
	}
}

watch(
	() => props.name,
	() => {
		page.value = null;
		shareNote.value = "";
		load();
	},
	{ immediate: true },
);
// usePagePanel bumps refreshKey when a write to this page lands.
watch(() => props.refreshKey, load);

function onScriptError(error) {
	logger.error("FAC Page script failed", error);
	scriptFailed.value = true;
}

function downloadPdf() {
	printPage({ title: title.value, ...view.value.printSnapshot() });
}

function share() {
	if (props.canShare) {
		emit("share", __("Share this page with my team"));
		return;
	}
	shareNote.value = __("A System Manager can share this page.");
}
</script>

<style scoped>
.page-panel {
	display: flex;
	flex-direction: column;
	height: 100%;
	min-height: 0;
	background: var(--ql-surface);
}
.page-panel-header {
	display: flex;
	align-items: center;
	gap: 12px;
	padding: 10px 14px;
	border-bottom: 1px solid var(--ql-border);
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
	font-family: var(--ql-font-mono);
	font-size: 11px;
	color: var(--ql-text-muted);
}
.page-panel-actions {
	display: flex;
	align-items: center;
	gap: 4px;
	flex: none;
}
.page-panel-action,
.page-panel-close,
.page-panel-back {
	padding: 5px 9px;
	border: none;
	border-radius: 6px;
	background: none;
	color: var(--ql-text-secondary);
	font-size: 13px;
	text-decoration: none;
	cursor: pointer;
}
.page-panel-action:hover:not(:disabled),
.page-panel-close:hover,
.page-panel-back:hover {
	background: var(--ql-subtle);
	color: var(--ql-text);
}
.page-panel-action:disabled {
	opacity: 0.5;
	cursor: default;
}
.page-panel-close {
	font-size: 18px;
	line-height: 1;
}
.page-panel-back {
	display: none;
}
.page-panel-note {
	margin: 0;
	padding: 8px 14px;
	border-bottom: 1px solid var(--ql-border);
	background: var(--ql-subtle);
	font-size: 13px;
	color: var(--ql-text-secondary);
}
.page-panel-open-desk {
	margin-left: 6px;
	color: var(--ql-accent);
	font-weight: 600;
}
.page-panel-body {
	flex: 1;
	min-height: 0;
	overflow: auto;
	padding: 16px;
}
.page-panel-message {
	margin: 0;
	font-size: 13px;
	color: var(--ql-text-muted);
}

/* Below 768 the panel is a full-screen overlay: a back control replaces the close button. */
@media (max-width: 767px) {
	.page-panel-header {
		flex-wrap: wrap;
	}
	.page-panel-back {
		display: inline-block;
		padding-left: 0;
	}
	.page-panel-close {
		display: none;
	}
	.page-panel-heading {
		order: 3;
		flex-basis: 100%;
	}
}
</style>
