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
	<div v-else ref="host" class="page-view-host" />
</template>

<script setup>
import DOMPurify from "dompurify";
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import { baseCall, getCall } from "@/api/_core";
import { usePagePanel } from "@/composables/usePagePanel";
import { fac_page_draft_srcdoc } from "@/utils/facPageDraft";
import { chart } from "@/utils/pageCharts";
import { snapshotHtml } from "@/utils/pagePrint";
import { makeFrappeStandIn, runPageScript } from "@/utils/pageRuntime";
// The one copy of the kit, also served to the fac-pages Desk page from /assets.
import kitCss from "../../../../../../public/css/mockup_kit.css?raw";

const props = defineProps({
	// get_page's response: {title, html, script, style, draft}.
	page: { type: Object, required: true },
	user: { type: String, default: "" },
	// The script waits for the user's Run new version: the page shows its html and style only.
	holdScript: { type: Boolean, default: false },
});

const emit = defineEmits(["unsupported", "error"]);

// A page wider than this prints on a landscape sheet.
const WIDE_PAGE_PX = 900;

const host = ref(null);
const draftFrame = ref(null);
// The charts this render drew; a newer version or a closed panel disposes them.
const charts = [];
const published = computed(() => props.page.draft === false);

const draftSrcdoc = computed(() =>
	fac_page_draft_srcdoc({ html: props.page.html, style: props.page.style, kit_css: kitCss }),
);

// Tags that embed another document or act on the whole one, dropped from a held page's html.
const HELD_FORBID_TAGS = ["iframe", "object", "embed", "base", "meta", "link"];

// Desk's create_shadow_element drops these from the html, so the page renders the same in both.
// get_page already serves a personal page's html without inline code; while its script is held,
// inline handlers and javascript: URLs are stripped here as well, so nothing runs before Run new
// version. DOMPurify's defaults keep forms and buttons, which the page's script may wire.
function pageFragment(html) {
	const template = document.createElement("template");
	const body = props.holdScript ? DOMPurify.sanitize(html || "", { FORBID_TAGS: HELD_FORBID_TAGS }) : html || "";
	template.innerHTML = `<div class="fac-page-root">${body}</div>`;
	template.content.querySelectorAll("script, style, link").forEach((el) => el.remove());
	return template.content;
}

// The page owns its shadow root: a key on this component, not a re-render, shows a newer version.
function render() {
	const root = host.value.attachShadow({ mode: "open" });
	const style = document.createElement("style");
	style.textContent = `${kitCss}\n${props.page.style || ""}`;
	root.append(style, pageFragment(props.page.html));
	if (!props.page.script || props.holdScript) return;

	const standIn = makeFrappeStandIn(
		{ baseCall, getCall, user: props.user },
		{ onUnsupported: (name) => emit("unsupported", name), onError: (error) => emit("error", error) },
	);
	const fac = {
		chart(el, option) {
			const handle = chart(el, option);
			charts.push(handle);
			return handle;
		},
	};
	const result = runPageScript(props.page.script, root, standIn, fac);
	if (result.error && !result.unsupported) emit("error", result.error);
}

// FACO's screenshot captures the page shown here; a draft's frame cannot be read.
let hidePageView = () => {};

onMounted(() => {
	if (published.value) render();
	const element = published.value ? host.value : draftFrame.value;
	hidePageView = usePagePanel().showPageView({
		element,
		draft: !published.value,
		codeWaiting: published.value && props.holdScript && Boolean(props.page.script),
	});
});

onBeforeUnmount(() => {
	hidePageView();
	charts.splice(0).forEach((handle) => handle.dispose());
});

// What Download PDF prints: the page as drawn now, after its script and charts ran. A draft's
// frame cannot be read from here, so it prints the sanitised html the frame shows.
function printSnapshot() {
	const base = { kitCss, style: props.page.style || "", draft: !published.value };
	if (!published.value) {
		const html = `<div class="fac-page-root">${props.page.html || ""}</div>`;
		return { ...base, html, wide: (draftFrame.value?.offsetWidth || 0) > WIDE_PAGE_PX };
	}
	const root = host.value.shadowRoot.querySelector(".fac-page-root");
	return { ...base, html: snapshotHtml(root), wide: root.scrollWidth > WIDE_PAGE_PX };
}

defineExpose({ printSnapshot });
</script>

<style scoped>
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
