<template>
	<section class="dr" data-test="discover-row" :aria-label="__('Discover what FAC can do')">
		<div class="dr-head">
			<h2 class="dr-heading">{{ __("Discover what FAC can do") }}</h2>
			<button type="button" class="dr-hide" data-test="discover-hide" @click="$emit('hide')">
				{{ __("Hide") }}
			</button>
		</div>
		<ul class="dr-grid">
			<li v-for="f in features" :key="f.id">
				<button
					type="button"
					class="dr-card"
					:data-test="`discover-${f.id}`"
					@click="$emit('open', f.id)"
				>
					<span class="dr-art">
						<FeaturePreviewArt :feature="f.id" />
						<span v-if="!tried.includes(f.id)" class="dr-new">{{ __("New for you") }}</span>
					</span>
					<span class="dr-text">
						<b>{{ f.title() }}</b>
						<small>{{ f.blurb() }}</small>
					</span>
				</button>
			</li>
		</ul>
	</section>
</template>

<script setup>
import { __ } from "@/utils/i18n";
import FeaturePreviewArt from "@/components/discover/FeaturePreviewArt.vue";

defineProps({
	features: { type: Array, required: true },
	tried: { type: Array, default: () => [] },
});
defineEmits(["open", "hide"]);
</script>

<style scoped>
.dr { text-align: left; min-width: 0; }
.dr-head { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: var(--ql-space-2); }
.dr-heading {
	margin: 0;
	font-size: var(--ql-label-size); font-weight: 600; text-transform: uppercase;
	letter-spacing: var(--ql-label-tracking); color: var(--ql-text-muted);
}
.dr-hide {
	border: 0; background: none; padding: 2px 4px; cursor: pointer;
	font-size: 12px; color: var(--ql-text-muted);
}
.dr-hide:hover { color: var(--ql-text); }
.dr-grid {
	margin: 0; padding: 0; list-style: none;
	display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px;
}
.dr-card {
	display: flex; flex-direction: column; width: 100%; height: 100%; padding: 0;
	border: 1px solid var(--ql-border); border-radius: 12px; overflow: hidden;
	background: var(--ql-surface); color: var(--ql-text); text-align: left; cursor: pointer;
	transition: border-color 0.15s ease, transform 0.15s ease;
}
.dr-card:hover { border-color: var(--ql-accent); transform: translateY(-1px); }
.dr-card:focus-visible { outline: 2px solid var(--ql-accent); outline-offset: 2px; }
.dr-art { position: relative; display: block; height: 74px; }
.dr-new {
	position: absolute; top: 7px; left: 7px; padding: 1px 7px; border-radius: 999px;
	background: var(--ql-gold); color: #2a2108; font-size: 10px; font-weight: 700;
}
.dr-text { display: block; padding: 9px 11px; }
.dr-text b { display: block; font-size: 13px; }
.dr-text small { display: block; margin-top: 2px; font-size: 11.5px; line-height: 1.35; color: var(--ql-text-muted); }
@media (prefers-reduced-motion: reduce) {
	.dr-card { transition: none; }
	.dr-card:hover { transform: none; }
}
</style>
