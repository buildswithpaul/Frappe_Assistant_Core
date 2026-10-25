<template>
	<aside v-if="openName" class="page-dock">
		<PagePanel
			:name="openName"
			:version="openChip?.version || 0"
			:pending="Boolean(openChip?.pending)"
			:can-share="canShare"
			:user="user"
			:refresh-key="refreshKey"
			@share="onShare"
		/>
	</aside>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, toRef, watch } from "vue";

import { usePagePanel } from "@/composables/usePagePanel";

import PagePanel from "./PagePanel.vue";

const props = defineProps({
	messages: { type: Array, default: () => [] },
	sessionId: { type: String, default: null },
	canShare: { type: Boolean, default: false },
	user: { type: String, default: "" },
});

const emit = defineEmits(["open", "share"]);

const { openName, refreshKey, chips, close, registerDock } = usePagePanel(toRef(props, "messages"));

// Chips open this panel only while it is mounted; elsewhere they link to Desk.
let unregister = () => {};
onMounted(() => (unregister = registerDock()));
onBeforeUnmount(() => unregister());

const openChip = computed(() => chips.value.find((chip) => chip.name === openName.value));

watch(openName, (name) => {
	if (name) emit("open", name);
});

// A page belongs to the conversation that made it; another conversation starts without one.
watch(
	() => props.sessionId,
	(id, previous) => {
		if (id !== previous) close();
	},
);

// The overlay covers the composer on a phone, so it steps aside for the text to send.
function onShare(text) {
	if (window.matchMedia?.("(max-width: 767px)").matches) close();
	emit("share", text);
}
</script>

<style scoped>
.page-dock {
	flex: 0 0 50%;
	min-width: 420px;
	height: 100%;
	overflow: hidden;
	border-left: 1px solid var(--ql-border);
}

@media (max-width: 767px) {
	.page-dock {
		position: fixed;
		inset: 0;
		z-index: 60;
		min-width: 0;
		border-left: none;
		padding-top: env(safe-area-inset-top, 0px);
		padding-bottom: env(safe-area-inset-bottom, 0px);
		background: var(--ql-surface);
	}
}
</style>
