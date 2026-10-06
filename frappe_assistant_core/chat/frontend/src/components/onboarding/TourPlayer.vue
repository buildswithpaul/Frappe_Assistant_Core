<script setup>
import { storeToRefs } from "pinia";
import { useTourStore } from "@/stores/tourStore";
import FeatureReel from "@/components/onboarding/FeatureReel.vue";
import { useTeleportTarget } from "@/composables/useTeleportTarget";

const teleportTarget = useTeleportTarget();

const tourStore = useTourStore();
const { isOpen } = storeToRefs(tourStore);

function onComplete() {
	tourStore.close();
}
</script>

<template>
	<Teleport :to="teleportTarget">
		<Transition name="tour-fade">
			<FeatureReel v-if="isOpen" @complete="onComplete" />
		</Transition>
	</Teleport>
</template>

<style scoped>
.tour-fade-enter-active, .tour-fade-leave-active {
	transition: opacity 280ms ease;
}
.tour-fade-enter-from, .tour-fade-leave-to {
	opacity: 0;
}
</style>
