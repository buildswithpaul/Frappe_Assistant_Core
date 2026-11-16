<template>
	<div class="notification-host">
		<OutageBanner />
		<HighPriorityBanner v-if="userStore.registrationStatus === 'ready'" />
	</div>
</template>

<script setup>
import { onMounted, onUnmounted, watch } from "vue";
import { useNotificationStore } from "@/stores/notificationStore";
import { useUserStore } from "@/stores/userStore";
import OutageBanner from "./OutageBanner.vue";
import HighPriorityBanner from "./HighPriorityBanner.vue";

const store = useNotificationStore();
const userStore = useUserStore();

onMounted(() => store.startPolling());
// A user can reach "ready" mid-session (Connect finishing, an invited user activated by first use).
watch(
	() => userStore.registrationStatus,
	(status) => {
		if (status === "ready") store.startPolling();
	},
);
onUnmounted(() => store.stopPolling());
</script>

<style scoped>
.notification-host {
	flex-shrink: 0;
}
</style>
