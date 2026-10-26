<template>
	<div ref="container" class="page-frame" />
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";

import { baseCall, getCall } from "@/api/_core";
import { createPageFrame, queryArgs } from "@/utils/pageFrameHost";

// A personal page ("Only me"): it runs at once, inside a frame that cannot act as the user.
const props = defineProps({
	// get_page's response: {title, html, script, style}.
	page: { type: Object, required: true },
	user: { type: String, default: "" },
	kitCss: { type: String, default: "" },
	// The FAC Page record name, which "Allow for this page" is scoped to.
	pageName: { type: String, default: "" },
	// Asks the user to allow a call; resolves "once", "page" or false.
	askUser: { type: Function, required: true },
});

const emit = defineEmits(["unsupported", "error", "ready"]);

const container = ref(null);
let frame = null;

// Set by the SPA build (vite.config.js); a test run has none.
const BUILD_ID = typeof __FAC_BUILD_ID__ !== "undefined" ? __FAC_BUILD_ID__ : "";

onMounted(() => {
	frame = createPageFrame({
		page: props.page,
		kitCss: props.kitCss,
		user: props.user,
		version: BUILD_ID,
		pageName: props.pageName,
		transport: {
			get: (method, args) => getCall(method, queryArgs(args)),
			post: (method, args) => baseCall(method, args),
		},
		askUser: (request) => props.askUser(request),
		onError: (message) => emit("error", new Error(message)),
		onUnsupported: (name) => emit("unsupported", name),
		onReady: () => emit("ready"),
	});
	container.value.append(frame.element);
});

onBeforeUnmount(() => frame?.dispose());

defineExpose({
	snapshot: () => frame.snapshot(),
	errors: () => frame?.errors || [],
});
</script>

<style scoped>
.page-frame {
	height: 100%;
}
.page-frame :deep(.fac-page-sandbox) {
	display: block;
	width: 100%;
	height: 100%;
	border: 0;
}
</style>
