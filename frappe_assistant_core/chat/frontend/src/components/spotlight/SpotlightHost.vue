<script setup>
import { onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { storeToRefs } from "pinia";
import { useSpotlightStore } from "@/stores/spotlightStore";
import { useNotificationStore } from "@/stores/notificationStore";
import { useUserStore } from "@/stores/userStore";
import { useTourStore } from "@/stores/tourStore";
import SpotlightModal from "./SpotlightModal.vue";

const router = useRouter();
const spotlight = useSpotlightStore();
const { current } = storeToRefs(spotlight);
const { notifications } = storeToRefs(useNotificationStore());
const { registrationStatus } = storeToRefs(useUserStore());
const { isOpen: tourOpen } = storeToRefs(useTourStore());

onMounted(() => spotlight.evaluate());
watch([notifications, registrationStatus, tourOpen], () => spotlight.evaluate());
</script>

<template>
	<SpotlightModal
		:content="current"
		@primary="spotlight.primary(router)"
		@secondary="spotlight.secondary(router)"
		@dismiss="spotlight.dismiss()"
	/>
</template>
