<template>
	<div class="cron-builder">
		<div class="presets">
			<button
				v-for="p in presets"
				:key="p.cron"
				class="preset-btn"
				:class="{ active: modelValue === p.cron }"
				@click="$emit('update:modelValue', p.cron)"
			>
				{{ p.label }}
			</button>
		</div>
		<div class="next-runs">
			<span class="next-runs-label">Next 3 runs</span>
			<ul v-if="nextRuns.length" class="runs-list">
				<li v-for="(run, i) in nextRuns" :key="i">{{ run }}</li>
			</ul>
			<p v-else class="custom-note">Custom expression</p>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({ modelValue: { type: String, default: "" } });
defineEmits(["update:modelValue"]);

const presets = [
	{ label: "Every hour", cron: "0 * * * *" },
	{ label: "Daily at 9am", cron: "0 9 * * *" },
	{ label: "Weekdays at 9am", cron: "0 9 * * 1-5" },
	{ label: "Weekly Monday", cron: "0 9 * * 1" },
];
const presetCrons = new Set(presets.map((p) => p.cron));

function parseDow(field) {
	const result = [];
	for (const part of field.split(",")) {
		if (part.includes("-")) {
			const [s, e] = part.split("-").map(Number);
			for (let i = s; i <= e; i++) result.push(i);
		} else result.push(Number(part));
	}
	return result;
}

function getNextRuns(cron) {
	if (!presetCrons.has(cron)) return [];
	const [minStr, hrStr, , , dowStr] = cron.split(" ");
	const minute = parseInt(minStr, 10);
	const hour = hrStr === "*" ? null : parseInt(hrStr, 10);
	const runs = [];
	const c = new Date();
	c.setSeconds(0, 0);
	c.setMinutes(c.getMinutes() + 1);
	for (let i = 0; runs.length < 3 && i < 400; i++) {
		if (hour !== null && c.getHours() !== hour) {
			if (c.getHours() > hour) c.setDate(c.getDate() + 1);
			c.setHours(hour, minute, 0, 0);
			continue;
		}
		if (c.getMinutes() !== minute) {
			if (c.getMinutes() > minute) c.setHours(c.getHours() + 1);
			c.setMinutes(minute, 0, 0);
			continue;
		}
		if (dowStr !== "*" && !parseDow(dowStr).includes(c.getDay())) {
			c.setDate(c.getDate() + 1);
			c.setHours(hour ?? 0, minute, 0, 0);
			continue;
		}
		runs.push(new Date(c));
		if (hour === null) c.setHours(c.getHours() + 1);
		else {
			c.setDate(c.getDate() + 1);
			c.setHours(hour, minute, 0, 0);
		}
	}
	return runs;
}

const fmt = (d) =>
	d.toLocaleString(undefined, {
		weekday: "short",
		month: "short",
		day: "numeric",
		hour: "2-digit",
		minute: "2-digit",
	});

const nextRuns = computed(() => {
	if (!props.modelValue) return [];
	return getNextRuns(props.modelValue).map(fmt);
});
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
.next-runs {
	padding: 0.5rem 0.625rem;
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
}
.next-runs-label {
	display: block;
	font-size: 0.6875rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	margin-bottom: 0.25rem;
	text-transform: uppercase;
	letter-spacing: 0.03em;
}
.runs-list {
	list-style: none;
	margin: 0;
	padding: 0;
	display: flex;
	flex-direction: column;
	gap: 0.125rem;
}
.runs-list li {
	font-size: 0.75rem;
	color: var(--ql-text);
}
.custom-note {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	font-style: italic;
	margin: 0;
}
</style>
