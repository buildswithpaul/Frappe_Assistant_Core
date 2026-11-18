<script setup>
import { __ } from "@/utils/i18n";
import { useTeleportTarget } from "@/composables/useTeleportTarget";

/** One line on a power's page for a first-timer: what to do here to try it. ✕ closes it for good. */
defineProps({ guide: { type: Object, required: true } });
defineEmits(["dismiss"]);
// Out of the rail's stacking context, beside the template list it must show above.
const teleportTarget = useTeleportTarget();
</script>

<template>
	<Teleport :to="teleportTarget">
		<div class="pg" role="status" data-test="power-guide" :data-guide="guide.id">
			<span class="pg-badge" aria-hidden="true">✦</span>
			<p class="pg-text"><b>{{ __("Your FAC") }}</b> {{ guide.text }}</p>
			<button
				type="button"
				class="pg-x"
				data-test="power-guide-dismiss"
				:aria-label="__('Close this guide')"
				@click="$emit('dismiss', guide.id)"
			>
				✕
			</button>
		</div>
	</Teleport>
</template>

<style scoped>
/* Above the template list (z-index 1000), so its guide shows while the list is open. */
.pg {
	position: fixed; z-index: 1002; left: 50%; bottom: 20px; transform: translateX(-50%);
	display: flex; align-items: center; gap: 10px; box-sizing: border-box;
	width: min(560px, calc(100vw - 32px)); padding: 10px 12px 10px 14px;
	border: 1px solid var(--ql-border); border-radius: 12px; background: var(--ql-surface);
	box-shadow: 0 8px 24px color-mix(in srgb, var(--ql-text) 14%, transparent);
}
.pg-badge { flex: none; color: var(--ql-accent); font-size: 14px; }
.pg-text { flex: 1; min-width: 0; margin: 0; font-size: 13px; line-height: 1.45; color: var(--ql-text-secondary); }
.pg-text b { color: var(--ql-text); font-weight: 600; margin-right: 4px; }
.pg-x {
	flex: none; padding: 4px 6px; border: 0; border-radius: 6px; background: none; cursor: pointer;
	color: var(--ql-text-muted); font-size: 12px;
}
.pg-x:hover { background: var(--ql-subtle); }
.pg-x:focus-visible { outline: 2px solid var(--ql-accent); outline-offset: 2px; }
</style>
