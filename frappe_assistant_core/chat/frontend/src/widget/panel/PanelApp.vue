<template>
	<div class="panel-shell">
		<WidgetSetupGate
			v-if="!ready"
			:status="userStore.registrationStatus"
			:is-admin="userStore.isAdmin"
			:user-setup-complete="userStore.isUserSetupComplete"
			:privacy-consent-complete="userStore.privacyConsentComplete"
		/>
		<WidgetPanel v-else />
		<ToastContainer />
	</div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, watch } from "vue";
import { storeToRefs } from "pinia";
import { useUserStore } from "@/stores/userStore";
import { useModelStore } from "@/stores/modelStore";
import { useChatStore } from "@/stores/chatStore";
import { useRobotMoodStore } from "@/stores/robotMoodStore";
import { useNotificationStore } from "@/stores/notificationStore";
import { useRobotMoodWiring } from "@/composables/useRobotMoodWiring";
import { useStreaming } from "@/composables/useStreaming";
import ToastContainer from "@/components/ui/ToastContainer.vue";
import WidgetPanel from "./WidgetPanel.vue";
import WidgetSetupGate from "./WidgetSetupGate.vue";
import { bridge } from "../bridge.js";
import { persistSession } from "../desk/session.js";
import { listenForConfirms } from "./confirmQueue.js";

const userStore = useUserStore();
const modelStore = useModelStore();
const chatStore = useChatStore();
const mood = useRobotMoodStore();
useRobotMoodWiring();
useStreaming();

// Listening starts now, not when the chat renders: a browser-tool confirmation can arrive
// while the panel is still bootstrapping, and a dropped one would never resolve.
const stopConfirms = listenForConfirms();
onUnmounted(stopConfirms);

// FAC Chat loads notifications through NotificationHost, which the panel does not mount.
// Without this the store stays empty and SpotlightHost never sees an announcement.
const notifications = useNotificationStore();
onMounted(() => notifications.startPolling());
onUnmounted(() => notifications.stopPolling());

const ready = computed(
	() =>
		userStore.registrationStatus === "ready" &&
		userStore.isUserSetupComplete &&
		userStore.privacyConsentComplete
);

onMounted(async () => {
	await userStore.init();
	// Widget turns always route automatically; pinned in memory only — never
	// setSelectedModel() or loadModels(), which would read or overwrite FAC Chat's saved choice.
	modelStore.pinModel("auto");
	modelStore.loadModels();
	if (!ready.value) return;
	if (bridge.state.restored) {
		await chatStore.loadMessages(bridge.state.sessionId);
	} else {
		chatStore.currentSessionId = bridge.state.sessionId;
	}
	chatStore.hydratePendingInterrupt(bridge.state.sessionId);
});

watch(
	() => chatStore.currentSessionId,
	(sid) => {
		if (!sid) return;
		persistSession(sid);
		bridge.emit("session", sid);
	}
);
const { activeMood } = storeToRefs(mood);
watch(activeMood, (m) => bridge.emit("mood", m), { immediate: true });
watch(
	() => chatStore.pendingInteractionBlock,
	(block) => (block ? bridge.emit("attention", block) : bridge.emit("attention-clear"))
);
</script>

<style scoped>
.panel-shell {
	height: 100%;
	display: flex;
	flex-direction: column;
	background: var(--ql-bg);
	color: var(--ql-text);
	font-family: var(--ql-font-sans);
	font-size: 14px;
	line-height: 1.55;
	border: 1px solid var(--ql-border);
	border-radius: 12px;
	box-shadow: 0 12px 40px rgba(0, 0, 0, 0.18);
	overflow: hidden;
}
</style>
