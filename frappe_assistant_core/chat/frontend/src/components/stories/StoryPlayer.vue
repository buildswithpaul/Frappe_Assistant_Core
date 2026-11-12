<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { __ } from "@/utils/i18n";
import { renderNotificationMarkdown } from "@/utils/markdown";
import { storySlides } from "@/components/discover/discoveryRules";
import SpotlightMedia from "@/components/spotlight/SpotlightMedia.vue";
import FeaturePreviewArt from "@/components/discover/FeaturePreviewArt.vue";

/**
 * A What's new story: a few full-screen slides written in AR. Plays on its own, pauses while
 * held, tap the left or right side to go back or on. Watching to the end, × or Escape all
 * close it as seen. Opened only by a tap on the rail bot or Watch in the bell, never by itself.
 */
const props = defineProps({ story: { type: Object, default: null } });
const emit = defineEmits(["close"]);
const router = useRouter();

const SLIDE_MS = 6000;
const TICK_MS = 50;

const slides = computed(() => storySlides(props.story));
const index = ref(0);
const elapsed = ref(0);
const paused = ref(false);
const dialog = ref(null);
const reduceMotion = typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
let timer = null;

const slide = computed(() => slides.value[index.value] || null);

function stop() {
	clearInterval(timer);
	timer = null;
}

function start() {
	stop();
	// With reduced motion nothing moves on its own: the user taps through.
	if (reduceMotion) return;
	timer = setInterval(() => {
		if (paused.value) return;
		elapsed.value += TICK_MS;
		if (elapsed.value >= SLIDE_MS) next();
	}, TICK_MS);
}

function go(i) {
	index.value = i;
	elapsed.value = 0;
}

function next() {
	if (index.value < slides.value.length - 1) go(index.value + 1);
	else close();
}

function prev() {
	go(Math.max(0, index.value - 1));
}

function close() {
	stop();
	emit("close");
}

function act(action) {
	close();
	router.push(action.route);
}

function fill(i) {
	if (i < index.value) return 1;
	if (i > index.value) return 0;
	return reduceMotion ? 1 : Math.min(1, elapsed.value / SLIDE_MS);
}

function onKeydown(e) {
	if (e.key === "Escape") close();
	else if (e.key === "ArrowRight") next();
	else if (e.key === "ArrowLeft") prev();
}

watch(
	() => props.story,
	async (story) => {
		if (!story || !slides.value.length) return stop();
		go(0);
		start();
		await nextTick();
		dialog.value?.focus();
	},
	{ immediate: true }
);
onBeforeUnmount(stop);
</script>

<template>
	<Teleport to="body">
		<div
			v-if="story && slide"
			ref="dialog"
			class="story"
			role="dialog"
			aria-modal="true"
			:aria-label="story.title || __('What\'s new')"
			tabindex="-1"
			data-test="story-player"
			@keydown="onKeydown"
		>
			<div class="story-frame" @pointerdown="paused = true" @pointerup="paused = false" @pointerleave="paused = false">
				<div class="story-bars" aria-hidden="true">
					<span v-for="(s, i) in slides" :key="i" class="story-bar">
						<span class="story-bar-fill" :style="{ transform: `scaleX(${fill(i)})` }"></span>
					</span>
				</div>
				<div class="story-head">
					<span class="story-eyebrow">{{ story.title || __("What's new") }}</span>
					<button type="button" class="story-x" :aria-label="__('Close')" data-test="story-close" @click="close">✕</button>
				</div>

				<div v-if="slide.media" class="story-media" data-test="story-media">
					<FeaturePreviewArt v-if="slide.media.art === 'feature'" :feature="slide.media.feature" />
					<SpotlightMedia v-else :media="slide.media" />
				</div>
				<div class="story-body" :class="{ 'story-body--alone': !slide.media }">
					<h2 class="story-title">{{ slide.title }}</h2>
					<div v-if="slide.message" class="story-text" v-html="renderNotificationMarkdown(slide.message)"></div>
					<button v-if="slide.action" type="button" class="story-cta" data-test="story-action" @click="act(slide.action)">
						{{ slide.action.label }}
					</button>
				</div>

				<button type="button" class="story-tap story-tap-prev" :aria-label="__('Previous')" @click="prev"></button>
				<button type="button" class="story-tap story-tap-next" :aria-label="__('Next')" data-test="story-next" @click="next"></button>
				<p class="story-count" aria-live="polite">{{ index + 1 }} / {{ slides.length }}</p>
			</div>
		</div>
	</Teleport>
</template>

<style scoped>
.story {
	position: fixed; inset: 0; z-index: 1000; display: flex; align-items: center; justify-content: center;
	background: color-mix(in srgb, #000 78%, transparent); outline: none;
}
.story-frame {
	position: relative; display: flex; flex-direction: column; width: min(400px, 100vw); height: min(700px, 100dvh);
	padding: 14px 16px 18px; box-sizing: border-box; overflow: hidden; border-radius: 18px;
	background: linear-gradient(170deg, var(--ql-surface), var(--ql-bg)); color: var(--ql-text);
	user-select: none;
}
@media (max-width: 480px) { .story-frame { border-radius: 0; } }
.story-bars { display: flex; gap: 4px; }
.story-bar { flex: 1; height: 3px; overflow: hidden; border-radius: 2px; background: color-mix(in srgb, var(--ql-text) 18%, transparent); }
.story-bar-fill { display: block; height: 100%; background: var(--ql-gold); transform-origin: left; }
.story-head { position: relative; z-index: 2; display: flex; align-items: center; justify-content: space-between; margin-top: 10px; }
.story-eyebrow { font-size: 12px; font-weight: 600; color: var(--ql-gold); }
.story-x { border: 0; background: none; color: var(--ql-text-muted); font-size: 16px; cursor: pointer; padding: 4px; }
.story-media { flex: 1; min-height: 0; margin: 14px 0; overflow: hidden; border-radius: 12px; }
.story-media :deep(img), .story-media :deep(video) { width: 100%; height: 100%; object-fit: cover; }
.story-body { position: relative; z-index: 2; margin-top: auto; }
/* A slide with no picture: its words sit in the middle, not under an empty box. */
.story-body--alone { margin-block: auto; text-align: center; }
.story-media :deep(.fpa) { height: 100%; }
.story-title { margin: 0 0 6px; font-size: 22px; line-height: 1.25; font-weight: 700; }
.story-text { font-size: 14px; line-height: 1.5; color: var(--ql-text-secondary); }
.story-text :deep(p) { margin: 0; }
.story-cta {
	margin-top: 14px; padding: 9px 16px; border: 0; border-radius: 10px; cursor: pointer;
	background: var(--ql-gold); color: #1a1a1a; font-size: 14px; font-weight: 700;
}
.story-tap { position: absolute; top: 60px; bottom: 120px; z-index: 1; width: 40%; border: 0; background: none; cursor: pointer; }
.story-tap-prev { left: 0; }
.story-tap-next { right: 0; }
.story-count { position: absolute; right: 16px; bottom: 8px; margin: 0; font-size: 11px; color: var(--ql-text-muted); }
.story-x:focus-visible, .story-cta:focus-visible, .story-tap:focus-visible { outline: 2px solid var(--ql-accent); outline-offset: 2px; }
</style>
