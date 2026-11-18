<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { __ } from "@/utils/i18n";
import { isPowerUsed, powerColor, ringSegments } from "./discoveryRules";

/**
 * Your FAC: the powers AR lists, which ones this user has really used, and a Try on the next one.
 * Opens from the progress ring on the rail bot; closes on Escape or a click outside.
 */
const props = defineProps({
	powers: { type: Array, required: true },
	used: { type: Array, required: true },
	progress: { type: Object, required: true },
});
const emit = defineEmits(["try", "close", "settings"]);
const panel = ref(null);

const rows = computed(() =>
	props.powers.map((p, i) => ({
		...p,
		done: isPowerUsed(p.id, props.used),
		next: props.progress.next?.id === p.id,
		color: powerColor(i),
	}))
);
// The big ring: one arc per power, each in its own colour once it is used.
const R = 33;
const CIRC = 2 * Math.PI * R;
const segments = computed(() => ringSegments(props.powers, props.used, { circ: CIRC, gap: 4 }));

function onDocPointer(e) {
	// The bot that opened the panel toggles it itself.
	if (panel.value && !panel.value.contains(e.target) && !e.target.closest?.("[data-test='rail-bot']")) emit("close");
}
function onKeydown(e) {
	if (e.key === "Escape") emit("close");
}

onMounted(async () => {
	document.addEventListener("pointerdown", onDocPointer);
	await nextTick();
	panel.value?.focus();
});
onBeforeUnmount(() => document.removeEventListener("pointerdown", onDocPointer));
</script>

<template>
	<section
		ref="panel"
		class="yf"
		role="dialog"
		:aria-label="__('Your FAC')"
		tabindex="-1"
		data-test="your-fac-panel"
		@keydown="onKeydown"
	>
		<h2 class="yf-title">{{ __("Your FAC") }}</h2>
		<div class="yf-ring" data-test="your-fac-ring">
			<svg viewBox="0 0 74 74" aria-hidden="true">
				<circle
					v-for="s in segments"
					:key="s.id"
					class="yf-seg"
					:class="{ done: s.done }"
					cx="37"
					cy="37"
					:r="R"
					:stroke-dasharray="s.dasharray"
					:stroke-dashoffset="s.dashoffset"
					:style="{ '--power-color': s.color }"
					:data-test="`your-fac-seg-${s.id}`"
				/>
			</svg>
			<span class="yf-ring-text">
				<b data-test="your-fac-count">{{ __("{0} of {1} powers", [progress.done, progress.total]) }}</b>
				<small data-test="your-fac-next">
					{{ progress.next ? __("Next: {0}", [progress.next.label]) : __("All done. Nice work.") }}
				</small>
			</span>
		</div>

		<ul class="yf-list">
			<li v-for="p in rows" :key="p.id" class="yf-row" :class="{ done: p.done, next: p.next }" :style="{ '--power-color': p.color }" :data-test="`power-${p.id}`">
				<span class="yf-mark" aria-hidden="true">{{ p.done ? "✓" : "" }}</span>
				<span class="yf-text">
					<span class="yf-label">{{ p.label }}<span v-if="p.done" class="sr-only">, {{ __("done") }}</span></span>
					<span v-if="p.description" class="yf-desc">{{ p.description }}</span>
				</span>
				<button
					v-if="!p.done"
					type="button"
					class="yf-try"
					:class="{ primary: p.next }"
					:data-test="`power-try-${p.id}`"
					@click="emit('try', p.id)"
				>
					{{ __("Try") }}
				</button>
			</li>
		</ul>

		<button type="button" class="yf-foot" @click="emit('settings')">{{ __("Turn this off in Settings → Home") }}</button>
	</section>
</template>

<style scoped>
.yf {
	position: fixed; z-index: 60; left: calc(var(--ql-rail-width, 52px) + 8px); top: 12px;
	width: min(320px, calc(100vw - var(--ql-rail-width, 52px) - 24px)); max-height: calc(100dvh - 24px); overflow-y: auto;
	padding: 16px; box-sizing: border-box; border: 1px solid var(--ql-border); border-radius: 14px;
	background: var(--ql-surface); box-shadow: 0 12px 32px color-mix(in srgb, var(--ql-text) 18%, transparent); outline: none;
}
.yf-title { margin: 0; font-size: 16px; font-weight: 700; color: var(--ql-text); }
.yf-ring { display: flex; align-items: center; gap: 14px; margin: 12px 0 14px; }
.yf-ring svg { flex: none; width: 74px; height: 74px; transform: rotate(-90deg); }
.yf-ring circle { fill: none; stroke-width: 7; }
.yf-seg { stroke: var(--ql-subtle); transition: stroke 0.4s ease; }
.yf-seg.done { stroke: var(--power-color); }
.yf-ring-text { display: flex; flex-direction: column; min-width: 0; }
.yf-ring-text b { font-family: var(--ql-font-display, Georgia, serif); font-size: 22px; font-weight: 600; line-height: 1.2; color: var(--ql-text); }
.yf-ring-text small { font-size: 12.5px; color: var(--ql-text-muted); }
@media (prefers-reduced-motion: reduce) { .yf-seg { transition: none; } }
.yf-list { margin: 0; padding: 0; list-style: none; }
.yf-row { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-top: 1px solid var(--ql-border); }
.yf-row:first-child { border-top: 0; }
.yf-mark {
	flex: none; display: flex; align-items: center; justify-content: center; width: 20px; height: 20px;
	border: 1.5px solid var(--ql-border); border-radius: 50%; font-size: 11px; font-weight: 700; color: var(--ql-bg);
}
/* Each power keeps its own colour: filled when done, an outline on the next one to try. */
.yf-row.done .yf-mark { border-color: var(--power-color); background: var(--power-color); }
.yf-row.next .yf-mark { border-color: var(--power-color); }
.yf-text { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.yf-label { font-size: 13.5px; font-weight: 600; color: var(--ql-text); }
.yf-row.done .yf-label { color: var(--ql-text-secondary); }
.yf-desc { font-size: 12px; color: var(--ql-text-muted); }
.yf-try {
	flex: none; padding: 4px 12px; border: 1px solid var(--ql-border); border-radius: 8px; cursor: pointer;
	background: none; color: var(--ql-text); font-size: 12.5px; font-weight: 600;
}
.yf-try.primary { border-color: transparent; background: var(--ql-text); color: var(--ql-bg); }
.yf-foot {
	margin-top: 10px; padding: 0; border: 0; background: none; cursor: pointer;
	font-size: 11.5px; color: var(--ql-text-muted); text-decoration: underline;
}
.yf-try:focus-visible, .yf-foot:focus-visible { outline: 2px solid var(--ql-accent); outline-offset: 2px; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
</style>
