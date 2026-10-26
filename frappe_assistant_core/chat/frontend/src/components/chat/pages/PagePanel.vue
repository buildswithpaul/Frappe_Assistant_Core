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

		<PageCodeReview
			v-if="page && waiting"
			:key="waitingKey"
			:state="waiting.review.state"
			:approved="waiting.review.approved"
			:script="waiting.data.script"
			:previous="Boolean(incoming)"
			@run="runNewVersion"
		/>

		<div class="page-panel-body" :class="{ 'is-held': page && review && !incoming }">
			<p v-if="loadFailed" class="page-panel-message">{{ __("This page could not be shown.") }}</p>
			<p v-else-if="!page" class="page-panel-message">{{ __("Loading…") }}</p>
			<template v-else>
				<p v-if="review && !incoming" class="page-panel-held-note">
					<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 8v4l2.5 2.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
					{{ __("The page fills in once you run its code.") }}
				</p>
				<PageView
					ref="view"
					:key="renderKey"
					:page="page"
					:user="user"
					:hold-script="Boolean(review)"
					:waiting-for="incoming ? waitingKey : 0"
					@unsupported="unsupported = $event"
					@error="onScriptError"
				/>
			</template>
		</div>
	</section>
</template>

<script setup>
import { computed, ref, watch } from "vue";

import { facPage } from "@/api/domains/facPage";
import { usePagePanel } from "@/composables/usePagePanel";
import { fac_page_approve_script, fac_page_script_review } from "@/utils/facPageApproval";
import { __ } from "@/utils/i18n";
import { logger } from "@/utils/logger";
import { printPage } from "@/utils/pagePrint";

import PageCodeReview from "./PageCodeReview.vue";
import PagePanelHeader from "./PagePanelHeader.vue";
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

// The page drawn, and why its script waits for the user (facPageApproval's review), or null when it runs.
const page = ref(null);
const review = ref(null);
// A newer version whose script waits, while the version the user last ran stays on screen:
// {data, review}. Only code the user already ran keeps running; this one runs on Run new version.
const incoming = ref(null);
// Bumped each time a version starts waiting, so the banner and FACO's screenshot follow it.
const waitingKey = ref(0);
const loadFailed = ref(false);
const unsupported = ref(null);
const scriptFailed = ref(false);
const shareNote = ref("");
const renderKey = ref(0);
const view = ref(null);
let request = 0;

const title = computed(() => page.value?.title || props.name);
// The version the banner is about: the newer one waiting, or the drawn page's held script.
const waiting = computed(() => incoming.value || (review.value && { data: page.value, review: review.value }));
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
		const nextReview = await fac_page_script_review(props.user, props.name, data);
		if (current !== request) return;
		if (nextReview && page.value && !review.value) {
			incoming.value = { data, review: nextReview };
			waitingKey.value++;
			return;
		}
		page.value = data;
		review.value = nextReview;
		incoming.value = null;
		if (nextReview) waitingKey.value++;
		renderKey.value++;
	} catch (error) {
		if (current !== request) return;
		logger.error("FAC Page could not be loaded", error);
		page.value = null;
		incoming.value = null;
		loadFailed.value = true;
	}
}

watch(
	() => props.name,
	() => {
		page.value = null;
		incoming.value = null;
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

// Approve the script the user was shown, then draw the page again with it running. Storage that
// cannot keep the approval still runs it now; the next open asks again.
async function runNewVersion() {
	const shown = incoming.value?.data || page.value;
	const name = props.name;
	await fac_page_approve_script(props.user, name, shown.script);
	if ((incoming.value?.data || page.value) !== shown || props.name !== name) return;
	page.value = shown;
	review.value = null;
	incoming.value = null;
	renderKey.value++;
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
/* A held page shows its layout only; it steps back so its empty figures read as waiting, not broken. */
.page-panel-body.is-held :deep(.page-view-frame) {
	opacity: 0.45;
	filter: grayscale(0.4);
	pointer-events: none;
	user-select: none;
}
.page-panel-held-note {
	display: flex;
	align-items: center;
	gap: 8px;
	margin: 0 2px 10px;
	font-size: 13px;
	color: var(--ql-text-secondary);
}
.page-panel-held-note svg {
	flex: none;
	width: 16px;
	height: 16px;
	fill: none;
	stroke: var(--ql-text-muted);
	stroke-width: 1.75;
	stroke-linecap: round;
	stroke-linejoin: round;
}

@media (max-width: 767px) {
	.page-panel-body {
		padding: 8px;
	}
}
</style>
