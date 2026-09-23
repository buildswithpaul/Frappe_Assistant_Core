<template>
	<!-- Bound as an object so a still icon carries no empty class attribute. -->
	<svg
		:width="size"
		:height="size"
		v-bind="spin ? { class: 'spin' } : {}"
		fill="none"
		stroke="currentColor"
		viewBox="0 0 24 24"
	>
		<path
			v-for="(d, i) in paths"
			:key="i"
			stroke-linecap="round"
			stroke-linejoin="round"
			stroke-width="2"
			:d="d"
		/>
	</svg>
</template>

<script setup>
import { computed } from "vue";

/** The toolbar's icon set. Every glyph shares the same 24-unit stroked grid. */
const ICON_PATHS = {
	back: ["M10 19l-7-7m0 0l7-7m-7 7h18"],
	play: [
		"M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z",
		"M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
	],
	pause: ["M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z"],
	spinner: [
		"M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15",
	],
	save: ["M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4"],
	clock: ["M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"],
	bolt: ["M13 10V3L4 14h7v7l9-11h-7z"],
	tag: [
		"M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z",
	],
	share: [
		"M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z",
	],
	gear: [
		"M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z",
		"M15 12a3 3 0 11-6 0 3 3 0 016 0z",
	],
	clipboard: [
		"M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2",
	],
	chart: [
		"M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z",
	],
};

const props = defineProps({
	name: { type: String, required: true },
	size: { type: [Number, String], default: 16 },
	spin: { type: Boolean, default: false },
});

const paths = computed(() => ICON_PATHS[props.name] || []);
</script>

<style scoped>
.spin {
	animation: spin 1s linear infinite;
}
@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}
</style>
