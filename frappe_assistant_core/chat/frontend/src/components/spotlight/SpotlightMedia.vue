<script setup>
import { computed, ref } from "vue";

defineProps({ media: { type: Object, required: true } });
const emit = defineEmits(["failed"]);
const failed = ref(false);
const reduceMotion = computed(
	() => typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
);

function onError() {
	failed.value = true;
	emit("failed");
}
</script>

<template>
	<div v-if="!failed" class="spot-media">
		<video
			v-if="media.type === 'video'"
			:src="media.url"
			:aria-label="media.alt"
			:autoplay="!reduceMotion || undefined"
			:controls="reduceMotion || undefined"
			muted
			loop
			playsinline
			preload="metadata"
			@error="onError"
		></video>
		<img v-else :src="media.url" :alt="media.alt" @error="onError" />
	</div>
</template>

<style scoped>
.spot-media {
	width: 100%;
	height: 100%;
	background: var(--ql-subtle);
}
.spot-media img,
.spot-media video {
	width: 100%;
	height: 100%;
	object-fit: cover;
	display: block;
}
</style>
