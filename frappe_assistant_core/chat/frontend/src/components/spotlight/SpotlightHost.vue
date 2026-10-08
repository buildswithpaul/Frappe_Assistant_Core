<script setup>
import { onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { storeToRefs } from "pinia";
import { useSpotlightStore } from "@/stores/spotlightStore";
import { useNotificationStore } from "@/stores/notificationStore";
import { useUserStore } from "@/stores/userStore";
import { useTourStore } from "@/stores/tourStore";
import SpotlightModal from "./SpotlightModal.vue";
import SpotlightCard from "./SpotlightCard.vue";

// The Desk widget renders inline: it shares the page with the user's Desk form, so a
// full-screen modal would cover their work.
defineProps({ inline: { type: Boolean, default: false } });

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
	<SpotlightCard
		v-if="inline"
		:content="current"
		@primary="spotlight.primary(router)"
		@secondary="spotlight.secondary(router)"
		@dismiss="spotlight.dismiss()"
	/>
	<SpotlightModal
		v-else
		:content="current"
		@primary="spotlight.primary(router)"
		@secondary="spotlight.secondary(router)"
		@dismiss="spotlight.dismiss()"
		@close="spotlight.close()"
	/>
</template>
