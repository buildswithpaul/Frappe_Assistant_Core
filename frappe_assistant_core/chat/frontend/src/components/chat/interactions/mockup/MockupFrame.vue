<template>
	<p v-if="tooLarge" class="mockup-too-large">{{ __("Mockup too large to show") }}</p>
	<iframe
		v-else
		ref="frame"
		sandbox="allow-scripts"
		:srcdoc="doc"
		:title="title"
		:style="{ height: `${height}px` }"
		class="mockup-frame"
	/>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import { __ } from "@/utils/i18n";
// The one copy of the kit, also served to the fac-pages Desk page from /assets.
import kitCss from "../../../../../../../public/css/mockup_kit.css?raw";

const MAX_BYTES = 200 * 1024;
const MIN_HEIGHT = 120;
const MAX_HEIGHT = 1200;

const CSP = "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:";
const HEIGHT_SCRIPT =
	"const post=()=>parent.postMessage({type:'mk-height',height:document.documentElement.scrollHeight},'*');" +
	"addEventListener('load',post);new ResizeObserver(post).observe(document.documentElement);";

const props = defineProps({
	html: { type: String, required: true },
	title: { type: String, default: "" },
});

const frame = ref(null);
const height = ref(MIN_HEIGHT);

const tooLarge = computed(() => new TextEncoder().encode(props.html).length > MAX_BYTES);

const doc = computed(
	() =>
		`<!doctype html><html><head><meta charset="utf-8">` +
		`<meta http-equiv="Content-Security-Policy" content="${CSP}">` +
		`<style>${kitCss}</style></head><body>${props.html}` +
		`<script>${HEIGHT_SCRIPT}<\/script></body></html>`,
);

// A sandboxed srcdoc frame has an opaque origin ("null"), so event.origin cannot identify it;
// the sender is verified by comparing event.source with this iframe's window instead.
function onMessage(event) {
	if (!frame.value || event.source !== frame.value.contentWindow) return;
	const data = event.data;
	if (!data || data.type !== "mk-height" || !Number.isFinite(data.height)) return;
	height.value = Math.min(Math.max(Math.ceil(data.height), MIN_HEIGHT), MAX_HEIGHT);
}

onMounted(() => window.addEventListener("message", onMessage));
onBeforeUnmount(() => window.removeEventListener("message", onMessage));
</script>

<style scoped>
.mockup-frame {
	width: 100%;
	border: 1px solid var(--outline-gray-2, #ededed);
	border-radius: 8px;
	background: #fff;
}

.mockup-too-large {
	margin: 0;
	font-size: 13px;
	color: var(--ink-gray-5, #7c7c7c);
}
</style>
