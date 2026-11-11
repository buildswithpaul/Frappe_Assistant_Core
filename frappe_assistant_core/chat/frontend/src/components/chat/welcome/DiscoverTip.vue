<template>
	<aside class="dt" data-test="discover-tip" :aria-label="__('Did you know?')">
		<span v-if="featureId" class="dt-art"><FeaturePreviewArt :feature="featureId" /></span>
		<p class="dt-text">
			<b>💡 {{ tip.title || __("Did you know?") }}</b> {{ tip.message }}
			<button
				v-if="tip.dismissible === true"
				type="button"
				class="dt-never"
				data-test="discover-tip-never"
				@click="$emit('never', tip.id)"
			>
				{{ __("Don't show this tip again") }}
			</button>
		</p>
		<button type="button" class="dt-show" data-test="discover-tip-show" @click="$emit('show', tip)">
			{{ __("Show me") }}
		</button>
		<button
			type="button"
			class="dt-x"
			data-test="discover-tip-dismiss"
			:aria-label="__('Hide this tip for today')"
			:title="__('Hide for today')"
			@click="$emit('hide')"
		>
			✕
		</button>
	</aside>
</template>

<script setup>
import { computed } from "vue";
import { __ } from "@/utils/i18n";
import FeaturePreviewArt from "@/components/discover/FeaturePreviewArt.vue";
import { featureById } from "@/components/discover/featureCatalog";

// One AR "tip" notification. The words come from AR; the moving preview is the feature's own, when the site has one.
const props = defineProps({ tip: { type: Object, required: true } });
defineEmits(["show", "hide", "never"]);

const featureId = computed(() => (props.tip.feature && featureById(props.tip.feature) ? props.tip.feature : null));
</script>

<style scoped>
.dt {
	display: flex; align-items: center; gap: 12px; padding: 10px 12px;
	border: 1px dashed var(--ql-border); border-radius: 12px; background: var(--ql-surface);
}
.dt-art { flex: none; width: 96px; height: 56px; border-radius: 8px; overflow: hidden; }
.dt-text { flex: 1; min-width: 0; margin: 0; font-size: 13px; line-height: 1.4; color: var(--ql-text); }
.dt-never {
	display: block; margin-top: 2px; padding: 0; border: 0; background: none; cursor: pointer;
	font-size: 11.5px; color: var(--ql-text-muted); text-decoration: underline;
}
.dt-show {
	flex: none; padding: 6px 12px; border: 0; border-radius: 9px; cursor: pointer;
	background: var(--ql-text); color: var(--ql-bg); font-size: 13px; font-weight: 600;
}
.dt-x { flex: none; border: 0; background: none; color: var(--ql-text-muted); font-size: 14px; cursor: pointer; }
.dt-show:focus-visible, .dt-x:focus-visible, .dt-never:focus-visible { outline: 2px solid var(--ql-accent); outline-offset: 2px; }
@media (max-width: 719px) {
	.dt { flex-wrap: wrap; }
	.dt-art { display: none; }
}
</style>
