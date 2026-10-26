<template>
	<section class="page-panel" :aria-label="title || __('Page')">
		<PagePanelHeader
			:title="title"
			:version="version"
			:pending="pending"
			:shareable="shareable"
			:desk-url="deskUrl"
			:pdf-disabled="!page"
			@close="close"
			@share="share"
			@pdf="downloadPdf"
		/>

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
			<PageWritePrompt
				v-if="writeAsk"
				:request="writeAsk.request"
				:total="writeQueue.length"
				@decide="decideWrite"
			/>
			<p v-if="loadFailed" class="page-panel-message">{{ __("This page could not be shown.") }}</p>
			<p v-else-if="!page" class="page-panel-message">{{ __("Loading…") }}</p>
			<PageView
				v-else
				ref="view"
				:key="renderKey"
				:page="page"
				:user="user"
				:page-name="name"
				:ask-user="askUser"
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

import PagePanelHeader from "./PagePanelHeader.vue";
import PageView from "./PageView.vue";
import PageWritePrompt from "./PageWritePrompt.vue";

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
// Calls a personal page asked to make, one shown at a time: {request, resolve}.
const writeQueue = ref([]);
const writeAsk = computed(() => writeQueue.value[0] || null);
let request = 0;

const title = computed(() => page.value?.title || props.name);
// Sharing is for the owner's personal page; a Shared page already is.
const shareable = computed(
	() => Boolean(page.value) && page.value.visibility !== "Shared" && page.value.owner_is_me !== false,
);
const deskUrl = computed(() => `/app/fac-pages/${encodeURIComponent(props.name)}`);

// A newer version replaces the page drawn, so a change the old one asked about is refused.
function refuseWrites() {
	writeQueue.value.splice(0).forEach((ask) => ask.resolve(false));
}

async function load() {
	const current = ++request;
	loadFailed.value = false;
	unsupported.value = null;
	scriptFailed.value = false;
	try {
		const data = await facPage.getPage(props.name);
		if (current !== request) return;
		if (!data || typeof data !== "object") throw new Error("get_page returned no page");
		refuseWrites();
		page.value = data;
		renderKey.value++;
	} catch (error) {
		if (current !== request) return;
		logger.error("FAC Page could not be loaded", error);
		refuseWrites();
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
// usePagePanel bumps refreshKey when a write to this page lands: the new version runs at once.
watch(() => props.refreshKey, load);

function onScriptError(error) {
	logger.error("FAC Page script failed", error);
	scriptFailed.value = true;
}

function askUser(request) {
	return new Promise((resolve) => writeQueue.value.push({ request, resolve }));
}

// "once", "page" or false.
function decideWrite(answer) {
	const ask = writeQueue.value.shift();
	ask?.resolve(answer);
}

async function downloadPdf() {
	try {
		printPage({ title: title.value, ...(await view.value.printSnapshot()) });
	} catch (error) {
		logger.error("FAC Page could not be printed", error);
		scriptFailed.value = true;
	}
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
.page-panel-note {
	margin: 0;
	padding: 8px 16px;
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
/* The page sits on the chat's background as a sheet, the way it prints. */
.page-panel-body {
	position: relative;
	display: flex;
	flex-direction: column;
	flex: 1;
	min-height: 0;
	padding: 14px;
	background: var(--ql-bg);
}
.page-panel-body > :deep(.page-view-frame),
.page-panel-body > :deep(.page-view-draft) {
	flex: 1;
	min-height: 0;
	height: auto;
}
.page-panel-message {
	margin: 0;
	padding: 4px 2px;
	font-size: 13px;
	color: var(--ql-text-muted);
}
@media (max-width: 767px) {
	.page-panel-body {
		padding: 8px;
	}
}
</style>
