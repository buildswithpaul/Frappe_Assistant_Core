<template>
	<div class="cron-builder" role="group" :aria-label="__('Common schedules')">
		<div class="presets">
			<button
				v-for="p in presets"
				:key="p.cron"
				type="button"
				class="preset-btn"
				:class="{ active: modelValue === p.cron }"
				@click="$emit('update:modelValue', p.cron)"
			>
				{{ p.label }}
			</button>
		</div>
	</div>
</template>

<script setup>
import { __ } from "@/utils/i18n";

defineProps({ modelValue: { type: String, default: "" } });
defineEmits(["update:modelValue"]);

// No "next runs" preview: it was computed in the browser's zone, so it was wrong
// for every schedule saved in another one.
const presets = [
	{ label: __("Every hour"), cron: "0 * * * *" },
	{ label: __("Daily at 9am"), cron: "0 9 * * *" },
	{ label: __("Weekdays at 9am"), cron: "0 9 * * 1-5" },
	{ label: __("Mondays at 9am"), cron: "0 9 * * 1" },
	{ label: __("1st of the month"), cron: "0 9 1 * *" },
];
</script>

<style scoped>
.cron-builder {
	display: flex;
	flex-direction: column;
	gap: 0.75rem;
}
.presets {
	display: flex;
	flex-wrap: wrap;
	gap: 0.375rem;
}
.preset-btn {
	padding: 0.3rem 0.625rem;
	font-size: 0.75rem;
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	background: var(--ql-surface);
	color: var(--ql-text);
	cursor: pointer;
	transition: all 0.15s ease;
}
.preset-btn:hover {
	border-color: var(--ql-accent);
	color: var(--ql-accent);
}
.preset-btn.active {
	background: var(--ql-accent);
	border-color: var(--ql-accent);
	color: #fff;
}
</style>
