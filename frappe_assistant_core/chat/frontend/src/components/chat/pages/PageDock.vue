<template>
	<aside v-if="openName" class="page-dock">
		<!-- FACO asks here before it captures the page below. -->
		<BrowserToolConfirm
			v-for="c in confirms"
			:key="c.id"
			:request="c.request"
			@decide="(decision) => settleConfirm(c, decision)"
		/>
		<PagePanel
			class="page-dock-panel"
			:name="openName"
			:version="openChip?.version || 0"
			:pending="Boolean(openChip?.pending)"
			:can-share="canShare"
			:user="user"
			:refresh-key="refreshKey"
			@share="onShare"
			@close="close"
		/>
	</aside>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, toRef, watch } from "vue";

import { isNarrow, usePagePanel } from "@/composables/usePagePanel";
import { useSpaBrowserTools } from "@/composables/useSpaBrowserTools";
import BrowserToolConfirm from "@/widget/panel/BrowserToolConfirm.vue";
import { confirms, settleConfirm } from "@/widget/panel/confirmQueue";

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

// A card nobody can see any more must not wait for an answer.
const denyCards = () => confirms.value.forEach((entry) => settleConfirm(entry, "deny"));

onBeforeUnmount(() => {
	unregister();
	denyCards();
});

const openChip = computed(() => chips.value.find((chip) => chip.name === openName.value));

useSpaBrowserTools({ getSessionId: () => props.sessionId });

watch(openName, (name) => {
	if (name) emit("open", name);
	// A closed page takes its cards with it, and leaves nothing to capture.
	else denyCards();
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
	if (isNarrow()) close();
	emit("share", text);
}
</script>

<style scoped>
.page-dock {
	display: flex;
	flex-direction: column;
	flex: 0 0 50%;
	min-width: 420px;
	height: 100%;
	overflow: hidden;
	border-left: 1px solid var(--ql-border);
}
.page-dock-panel {
	flex: 1;
	min-height: 0;
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
