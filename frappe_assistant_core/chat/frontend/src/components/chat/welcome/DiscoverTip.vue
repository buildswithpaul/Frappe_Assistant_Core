<template>
	<aside class="dt" data-test="discover-tip" :aria-label="__('Did you know?')">
		<span class="dt-art"><FeaturePreviewArt :feature="feature.id" /></span>
		<p class="dt-text">
			<b>{{ __("Did you know?") }}</b> {{ feature.popupBody() }}
			<small>{{ feature.title() }}</small>
		</p>
		<button type="button" class="dt-show" data-test="discover-tip-show" @click="$emit('open', feature.id)">
			{{ __("Show me") }}
		</button>
		<button
			type="button"
			class="dt-x"
			data-test="discover-tip-dismiss"
			:aria-label="__('Dismiss tip')"
			@click="$emit('dismiss', feature.id)"
		>
			✕
		</button>
	</aside>
</template>

<script setup>
import { __ } from "@/utils/i18n";
import FeaturePreviewArt from "@/components/discover/FeaturePreviewArt.vue";

defineProps({ feature: { type: Object, required: true } });
defineEmits(["open", "dismiss"]);
</script>

<style scoped>
.dt {
	display: flex; align-items: center; gap: 12px; padding: 10px 12px;
	border: 1px dashed var(--ql-border); border-radius: 12px; background: var(--ql-surface);
}
.dt-art { flex: none; width: 96px; height: 56px; border-radius: 8px; overflow: hidden; }
.dt-text { flex: 1; min-width: 0; margin: 0; font-size: 13px; line-height: 1.4; color: var(--ql-text); }
.dt-text small { display: block; margin-top: 2px; font-size: 11.5px; color: var(--ql-text-muted); }
.dt-show {
	flex: none; padding: 6px 12px; border: 0; border-radius: 9px; cursor: pointer;
	background: var(--ql-text); color: var(--ql-bg); font-size: 13px; font-weight: 600;
}
.dt-x { flex: none; border: 0; background: none; color: var(--ql-text-muted); font-size: 14px; cursor: pointer; }
.dt-show:focus-visible, .dt-x:focus-visible { outline: 2px solid var(--ql-accent); outline-offset: 2px; }
@media (max-width: 719px) {
	.dt { flex-wrap: wrap; }
	.dt-art { display: none; }
}
</style>
