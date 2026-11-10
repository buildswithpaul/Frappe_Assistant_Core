<script setup>
// The first-login tour: three stops that show WHERE things are (the composer, the
// "Needs you" cards, the left rail), not how every feature works. Skippable, and
// replayable from Settings → Help → "Show me around". A stop whose element is not
// on screen (Needs you switched off, the rail on a phone) is left out.
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { __ } from "@/utils/i18n";
import { useTeleportTarget } from "@/composables/useTeleportTarget";
import { COACH_STOPS } from "./featureCatalog";

const props = defineProps({ active: { type: Boolean, default: false } });
const emit = defineEmits(["done"]);
const teleportTarget = useTeleportTarget();

const PAD = 6;
const CARD_W = 280;
const stops = ref([]);
const index = ref(0);
const rect = ref(null);
const nextRef = ref(null);

const stop = computed(() => stops.value[index.value] || null);
const isLast = computed(() => index.value >= stops.value.length - 1);

function visible(el) {
	if (!el) return false;
	const r = el.getBoundingClientRect();
	return r.width > 0 && r.height > 0;
}

function measure() {
	const el = stop.value && document.querySelector(stop.value.selector);
	rect.value = visible(el) ? el.getBoundingClientRect() : null;
}

const holeStyle = computed(() => {
	const r = rect.value;
	if (!r) return {};
	return {
		top: `${r.top - PAD}px`,
		left: `${r.left - PAD}px`,
		width: `${r.width + PAD * 2}px`,
		height: `${r.height + PAD * 2}px`,
	};
});

const cardStyle = computed(() => {
	const r = rect.value;
	if (!r) return {};
	const vw = window.innerWidth;
	const vh = window.innerHeight;
	let left = stop.value.place === "right" ? r.right + 14 : r.left;
	let top = stop.value.place === "right" ? r.top + 12 : r.bottom + 14;
	left = Math.max(12, Math.min(left, vw - CARD_W - 12));
	top = Math.max(12, Math.min(top, vh - 170));
	return { left: `${left}px`, top: `${top}px`, width: `${CARD_W}px` };
});

async function start() {
	await nextTick();
	stops.value = COACH_STOPS.filter((s) => visible(document.querySelector(s.selector)));
	index.value = 0;
	if (!stops.value.length) {
		finish();
		return;
	}
	const el = document.querySelector(stops.value[0].selector);
	el?.scrollIntoView?.({ block: "nearest" });
	measure();
	window.addEventListener("resize", measure);
	window.addEventListener("scroll", measure, true);
	await nextTick();
	nextRef.value?.focus();
}

function cleanup() {
	window.removeEventListener("resize", measure);
	window.removeEventListener("scroll", measure, true);
}

function finish() {
	cleanup();
	stops.value = [];
	emit("done");
}

async function next() {
	if (isLast.value) {
		finish();
		return;
	}
	index.value++;
	document.querySelector(stop.value.selector)?.scrollIntoView?.({ block: "nearest" });
	measure();
	await nextTick();
	nextRef.value?.focus();
}

watch(
	() => props.active,
	(on) => (on ? start() : cleanup()),
	{ immediate: true }
);
onBeforeUnmount(cleanup);
</script>

<template>
	<Teleport :to="teleportTarget">
		<div
			v-if="active && stop && rect"
			class="coach-layer"
			data-test="coach-tour"
			@keydown.esc.prevent="finish"
		>
			<div class="coach-hole" :style="holeStyle"></div>
			<div
				class="coach-card"
				role="dialog"
				aria-modal="true"
				:aria-label="stop.title()"
				:style="cardStyle"
			>
				<h4>{{ stop.title() }}</h4>
				<p>{{ stop.text() }}</p>
				<div class="coach-foot">
					<span>
						{{ __("{0} of {1}", [index + 1, stops.length]) }} ·
						<button type="button" class="coach-skip" data-test="coach-skip" @click="finish">
							{{ __("Skip tour") }}
						</button>
					</span>
					<button ref="nextRef" type="button" class="coach-next" data-test="coach-next" @click="next">
						{{ isLast ? __("Done") : __("Next") }}
					</button>
				</div>
			</div>
		</div>
	</Teleport>
</template>

<style scoped>
.coach-layer { position: fixed; inset: 0; z-index: 990; }
.coach-hole {
	position: fixed;
	border-radius: 12px;
	box-shadow: 0 0 0 9999px rgba(18, 20, 22, 0.45), 0 0 0 3px var(--ql-gold);
	pointer-events: none;
	transition: all 0.25s ease;
}
.coach-card {
	position: fixed;
	padding: 13px 14px;
	border-radius: 12px;
	background: var(--ql-surface);
	color: var(--ql-text);
	box-shadow: 0 12px 32px rgba(0, 0, 0, 0.25);
}
.coach-card h4 { margin: 0 0 3px; font-size: 14px; }
.coach-card p { margin: 0; font-size: 13px; color: var(--ql-text-secondary); }
.coach-foot {
	display: flex; justify-content: space-between; align-items: center; gap: 8px;
	margin-top: 10px; font-size: 12px; color: var(--ql-text-muted);
}
.coach-skip { border: 0; background: none; padding: 0; color: inherit; text-decoration: underline; cursor: pointer; font-size: 12px; }
.coach-next {
	padding: 6px 14px; border: 0; border-radius: 9px; cursor: pointer;
	background: var(--ql-text); color: var(--ql-bg); font-size: 13px; font-weight: 600;
}
.coach-next:focus-visible, .coach-skip:focus-visible { outline: 2px solid var(--ql-accent); outline-offset: 2px; }
@media (prefers-reduced-motion: reduce) {
	.coach-hole { transition: none; }
}
</style>
