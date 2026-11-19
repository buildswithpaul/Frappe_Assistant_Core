<template>
	<div class="s-controls">
		<ul v-if="warnings.length" class="tool-list">
			<li v-for="w in warnings" :key="`${w.user}:${w.server}:${w.tool}`" class="s-row">
				<code class="tool-name">{{ w.tool }}</code>
				<button
					v-if="canAllow(w)"
					type="button"
					class="s-btn"
					data-test="allow-tool"
					:disabled="busy"
					@click="$emit('allow', w)"
				>
					{{ __("Allow unattended") }}
				</button>
			</li>
		</ul>
		<p v-if="othersToAsk.length" class="s-hint" data-test="ask-runtime-user">
			{{
				__("Ask {0} to set these to Always allow in Settings → Connections.", [othersToAsk.join(", ")])
			}}
		</p>
		<p v-if="note" class="s-hint">{{ note }}</p>
		<button type="button" class="s-link" :disabled="busy" @click="$emit('recheck')">
			{{ busy ? __("Checking…") : __("Check again") }}
		</button>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { __ } from "@/utils/i18n";

const props = defineProps({
	warnings: { type: Array, default: () => [] },
	currentUser: { type: String, default: "" },
	/** Tools whose preference was saved but still read as not allowed. */
	stuck: { type: Array, default: () => [] },
	note: { type: String, default: "" },
	busy: { type: Boolean, default: false },
});
defineEmits(["allow", "recheck"]);

// Only the runtime user can approve their own tools.
const canAllow = (w) => w.user === props.currentUser && !props.stuck.includes(w.tool);

const othersToAsk = computed(() => [
	...new Set(props.warnings.filter((w) => !canAllow(w)).map((w) => w.user || __("the runtime user"))),
]);
</script>

<style scoped src="./setupControls.css"></style>
<style scoped>
.tool-list {
	display: flex;
	flex-direction: column;
	gap: 0.25rem;
}
.tool-name {
	flex: 1;
	min-width: 0;
	font-size: 0.75rem;
	overflow-wrap: anywhere;
}
</style>
