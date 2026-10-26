<template>
	<!-- A draft is dormant: no script, sanitised html, and a frame that can run nothing. Only a
	     page that says it is not a draft runs, so a response missing the flag fails closed. -->
	<iframe
		v-if="!published"
		ref="draftFrame"
		sandbox=""
		class="page-view-draft"
		:title="page.title"
		:srcdoc="draftSrcdoc"
	/>
	<!-- A personal page runs at once, in a frame that reads as the user and asks before a change.
	     Only a page that says it is Shared runs beside the chat, so a missing flag fails closed. -->
	<div v-else-if="personal" class="page-view-frame">
		<PageFrame
			ref="personalFrame"
			:page="page"
			:user="user"
			:kit-css="kitCss"
			:page-name="pageName"
			:ask-user="askUser"
			@unsupported="emit('unsupported', $event)"
			@error="onError"
		/>
	</div>
	<div v-else class="page-view-frame">
		<div ref="host" class="page-view-host" />
	</div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import { baseCall, getCall } from "@/api/_core";
import { usePagePanel } from "@/composables/usePagePanel";
import { fac_page_draft_srcdoc } from "@/utils/facPageDraft";
import { chart } from "@/utils/pageCharts";
import { snapshotHtml } from "@/utils/pagePrint";
import { cleanSnapshot } from "@/utils/pageSnapshotSanitise";
import { makeFrappeStandIn, runPageScript } from "@/utils/pageRuntime";
// The one copy of the kit, also served to the fac-pages Desk page from /assets.
import kitCss from "../../../../../../public/css/mockup_kit.css?raw";

import PageFrame from "./PageFrame.vue";

const props = defineProps({
	// get_page's response: {title, html, script, style, draft, visibility}.
	page: { type: Object, required: true },
	user: { type: String, default: "" },
	// The FAC Page record name, which a personal page's "Allow for this page" is scoped to.
	pageName: { type: String, default: "" },
	// Asks the user to allow a call a personal page wants to make; resolves "once", "page" or false.
	askUser: { type: Function, default: () => Promise.resolve(false) },
});

const emit = defineEmits(["unsupported", "error"]);

// A page wider than this prints on a landscape sheet.
const WIDE_PAGE_PX = 900;

const host = ref(null);
const draftFrame = ref(null);
const personalFrame = ref(null);
// The charts this render drew; a newer version or a closed panel disposes them.
const charts = [];
// What went wrong while this version ran, for FACO's screenshot to report.
const errors = [];
const published = computed(() => props.page.draft === false);
const personal = computed(() => published.value && props.page.visibility !== "Shared");

const draftSrcdoc = computed(() =>
	fac_page_draft_srcdoc({ html: props.page.html, style: props.page.style, kit_css: kitCss }),
);

function onError(error) {
	if (errors.length < 20) errors.push(String(error?.message || error));
	emit("error", error);
}

// Desk's create_shadow_element drops these from the html, so the page renders the same in both.
function pageFragment(html) {
	const template = document.createElement("template");
	template.innerHTML = `<div class="fac-page-root">${html || ""}</div>`;
	template.content.querySelectorAll("script, style, link").forEach((el) => el.remove());
	return template.content;
}

// A Shared page, published through the go-live card that showed its code, runs in the chat as in
// Desk. The page owns its shadow root: a key on this component, not a re-render, shows a newer version.
function renderShared() {
	const root = host.value.attachShadow({ mode: "open" });
	const style = document.createElement("style");
	style.textContent = `${kitCss}\n${props.page.style || ""}`;
	root.append(style, pageFragment(props.page.html));
	if (!props.page.script) return;

	const standIn = makeFrappeStandIn(
		{ baseCall, getCall, user: props.user },
		{ onUnsupported: (name) => emit("unsupported", name), onError },
	);
	const fac = {
		chart(el, option) {
			const handle = chart(el, option);
			charts.push(handle);
			return handle;
		},
	};
	const result = runPageScript(props.page.script, root, standIn, fac);
	if (result.error && !result.unsupported) onError(result.error);
}

// FACO's screenshot captures the page shown here; a draft's frame cannot be read.
let hidePageView = () => {};

// A personal page's picture is drawn inside its own frame; only the image bytes come back.
const capturePersonal = (options) => personalFrame.value.capture(options);

onMounted(() => {
	if (published.value && !personal.value) renderShared();
	hidePageView = usePagePanel().showPageView({
		element: personal.value ? null : published.value ? host.value : draftFrame.value,
		draft: !published.value,
		capture: personal.value ? capturePersonal : null,
		errors: () => (personal.value ? personalFrame.value?.errors() || [] : errors),
	});
});

onBeforeUnmount(() => {
	hidePageView();
	charts.splice(0).forEach((handle) => handle.dispose());
});

// What Download PDF prints: the page as drawn now, after its script and charts ran. A draft's
// frame cannot be read from here, so it prints the sanitised html the frame shows.
async function printSnapshot() {
	const base = { kitCss, style: props.page.style || "", draft: !published.value, personal: personal.value };
	if (!published.value) {
		const html = `<div class="fac-page-root">${props.page.html || ""}</div>`;
		return { ...base, html, wide: (draftFrame.value?.offsetWidth || 0) > WIDE_PAGE_PX };
	}
	if (personal.value) {
		// The page's script wrote this markup: off-site URLs go before this window draws it.
		const { html, wide } = await personalFrame.value.snapshot();
		return { ...base, html: cleanSnapshot(html), wide };
	}
	const root = host.value.shadowRoot.querySelector(".fac-page-root");
	return { ...base, html: snapshotHtml(root), wide: root.scrollWidth > WIDE_PAGE_PX };
}

defineExpose({ printSnapshot });
</script>

<style scoped>
/* The page's box: its style and its script's elements paint inside it and nowhere else, so a fixed
   element cannot cover the chat. Paint containment makes the box the containing block of fixed
   elements and clips them. It is set here, outside the shadow host, where the page's own :host
   rules cannot undo it. The box scrolls the page, so a wide page still scrolls sideways. A
   personal page's frame scrolls inside itself. The page is a light document in either theme, on
   the kit's white, as it prints. */
.page-view-frame {
	height: 100%;
	overflow: auto;
	contain: layout paint;
	isolation: isolate;
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-lg);
	background: #fff;
}
.page-view-host {
	display: block;
	min-height: 100%;
}
.page-view-draft {
	display: block;
	width: 100%;
	height: 100%;
	min-height: 480px;
	border: 0;
}
</style>
