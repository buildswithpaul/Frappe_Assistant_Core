<template>
	<!-- A draft is dormant: no script, sanitised html, and a frame that can run nothing. Only a
	     page that says it is not a draft runs, so a response missing the flag fails closed. -->
	<iframe
		v-if="!published"
		sandbox=""
		class="page-view-draft"
		:title="page.title"
		:srcdoc="draftSrcdoc"
	/>
	<div v-else ref="host" class="page-view-host" />
</template>

<script setup>
import { computed, onMounted, ref } from "vue";

import { baseCall, getCall } from "@/api/_core";
import { fac_page_draft_srcdoc } from "@/utils/facPageDraft";
import { makeFrappeStandIn, runPageScript } from "@/utils/pageRuntime";
// The one copy of the kit, also served to the fac-pages Desk page from /assets.
import kitCss from "../../../../../../public/css/mockup_kit.css?raw";

const props = defineProps({
	// get_page's response: {title, html, script, style, draft}.
	page: { type: Object, required: true },
	user: { type: String, default: "" },
});

const emit = defineEmits(["unsupported", "error"]);

const host = ref(null);
const published = computed(() => props.page.draft === false);

const draftSrcdoc = computed(() =>
	fac_page_draft_srcdoc({ html: props.page.html, style: props.page.style, kit_css: kitCss }),
);

// Desk's create_shadow_element drops these from the html, so the page renders the same in both.
function pageFragment(html) {
	const template = document.createElement("template");
	template.innerHTML = `<div class="fac-page-root">${html || ""}</div>`;
	template.content.querySelectorAll("script, style, link").forEach((el) => el.remove());
	return template.content;
}

// The page owns its shadow root: a key on this component, not a re-render, shows a newer version.
function render() {
	const root = host.value.attachShadow({ mode: "open" });
	const style = document.createElement("style");
	style.textContent = `${kitCss}\n${props.page.style || ""}`;
	root.append(style, pageFragment(props.page.html));
	if (!props.page.script) return;

	const standIn = makeFrappeStandIn(
		{ baseCall, getCall, user: props.user },
		{ onUnsupported: (name) => emit("unsupported", name), onError: (error) => emit("error", error) },
	);
	const result = runPageScript(props.page.script, root, standIn);
	if (result.error && !result.unsupported) emit("error", result.error);
}

onMounted(() => {
	if (published.value) render();
});
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
