<template>
	<form class="s-controls" data-test="schedule-picker" @submit.prevent="save">
		<template v-if="!advanced">
			<div class="s-row">
				<select v-model="simple.freq" class="s-input" data-test="schedule-freq" :aria-label="__('How often')">
					<option value="hourly">{{ __("Every hour") }}</option>
					<option value="daily">{{ __("Every day") }}</option>
					<option value="weekdays">{{ __("Weekdays") }}</option>
					<option value="weekly">{{ __("Every week") }}</option>
					<option value="monthly">{{ __("Every month") }}</option>
				</select>
				<select
					v-if="simple.freq === 'weekly'"
					v-model.number="simple.weekday"
					class="s-input"
					data-test="schedule-weekday"
					:aria-label="__('Day of the week')"
				>
					<option v-for="(day, i) in WEEKDAYS()" :key="i" :value="i">{{ day }}</option>
				</select>
				<select
					v-if="simple.freq === 'monthly'"
					v-model.number="simple.monthday"
					class="s-input"
					:aria-label="__('Day of the month')"
				>
					<option v-for="d in 28" :key="d" :value="d">{{ __("Day {0}", [d]) }}</option>
				</select>
				<input
					v-if="simple.freq !== 'hourly'"
					v-model="time"
					type="time"
					class="s-input"
					data-test="schedule-time"
					:aria-label="__('Time')"
				/>
				<select
					v-else
					v-model.number="simple.minute"
					class="s-input"
					:aria-label="__('Minute past the hour')"
				>
					<option v-for="m in [0, 15, 30, 45]" :key="m" :value="m">:{{ String(m).padStart(2, "0") }}</option>
				</select>
			</div>
		</template>
		<template v-else>
			<input
				v-model.trim="cron"
				class="s-input mono"
				data-test="schedule-cron"
				placeholder="0 9 * * 1"
				:aria-label="__('Cron expression')"
			/>
			<textarea
				v-model="defaultInput"
				class="s-input mono"
				rows="2"
				:placeholder="__('Input for scheduled runs (optional)')"
			></textarea>
		</template>
		<div class="s-row">
			<select v-model="timezone" class="s-input s-grow" data-test="schedule-tz" :aria-label="__('Timezone')">
				<option v-for="tz in zones" :key="tz" :value="tz">{{ tz }}</option>
			</select>
		</div>
		<div class="s-row">
			<button type="submit" class="s-btn primary" data-test="schedule-save" :disabled="!canSave">
				{{ __("Save schedule") }}
			</button>
			<button type="button" class="s-link" data-test="schedule-advanced" @click="toggleAdvanced">
				{{ advanced ? __("Simple") : __("Advanced") }}
			</button>
			<button v-if="cancellable" type="button" class="s-link" @click="$emit('cancel')">{{ __("Cancel") }}</button>
		</div>
		<p v-if="advanced && cron && !looksValid" class="s-error">{{ __("A cron expression has five parts.") }}</p>
	</form>
</template>

<script setup>
import { computed, reactive, ref } from "vue";
import { __ } from "@/utils/i18n";
import { parseCron, toCron, WEEKDAYS, zoneOptions } from "../scheduleWords";

const props = defineProps({
	schedule: { type: Object, required: true },
	/** The zone to show: the proposed one for an imported UTC schedule. */
	initialTimezone: { type: String, default: "UTC" },
	saving: { type: Boolean, default: false },
	cancellable: { type: Boolean, default: false },
});
const emit = defineEmits(["save", "cancel"]);

const parsed = parseCron(props.schedule.cron);
const advanced = ref(!!props.schedule.cron && !parsed);
const simple = reactive({ freq: "daily", hour: 9, minute: 0, weekday: 1, monthday: 1, ...(parsed || {}) });
const cron = ref(props.schedule.cron || "");
const defaultInput = ref(props.schedule.defaultInput || "");
const timezone = ref(props.initialTimezone);
const zones = computed(() => zoneOptions(timezone.value, props.initialTimezone));

const pad = (n) => String(n).padStart(2, "0");
const time = computed({
	get: () => `${pad(simple.hour)}:${pad(simple.minute)}`,
	set: (value) => {
		const [h, m] = (value || "09:00").split(":").map(Number);
		simple.hour = h;
		simple.minute = m;
	},
});

const looksValid = computed(() => cron.value.split(/\s+/).length === 5);
const nextCron = computed(() => (advanced.value ? cron.value : toCron(simple)));
const canSave = computed(() => !props.saving && !!nextCron.value && (!advanced.value || looksValid.value));

function toggleAdvanced() {
	if (!advanced.value) cron.value = toCron(simple);
	else {
		const read = parseCron(cron.value);
		if (read) Object.assign(simple, read);
	}
	advanced.value = !advanced.value;
}

function save() {
	if (!canSave.value) return;
	emit("save", { cron: nextCron.value, timezone: timezone.value, defaultInput: defaultInput.value });
}
</script>

<style scoped src="./setupControls.css"></style>
<style scoped>
.mono {
	font-family: var(--ql-font-mono, ui-monospace, monospace);
}
</style>
