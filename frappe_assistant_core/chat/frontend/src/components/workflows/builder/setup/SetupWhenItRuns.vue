<template>
	<div class="s-controls">
		<section class="when-section" :aria-label="__('On a schedule')">
			<p class="when-title">{{ __("On a schedule") }}</p>
			<SchedulePicker
				v-if="editingSchedule"
				:key="schedule.cron"
				:schedule="schedule"
				:initial-timezone="initialTimezone"
				:saving="saving"
				:cancellable="!!schedule.cron || triggers.length > 0"
				@save="onSave"
				@cancel="editingSchedule = false"
			/>
			<div v-else-if="schedule.cron" class="s-row">
				<span class="when-line">{{ describeSchedule(schedule.cron, initialTimezone) }}</span>
				<span class="badge" :class="{ on: schedule.enabled }">{{ schedule.enabled ? __("on") : __("off") }}</span>
				<button type="button" class="s-link" data-test="schedule-change" @click="editingSchedule = true">
					{{ __("Change") }}
				</button>
			</div>
			<button v-else type="button" class="s-link" data-test="schedule-add" @click="editingSchedule = true">
				{{ __("Add a schedule") }}
			</button>
		</section>

		<section class="when-section" :aria-label="__('When a document changes')">
			<p class="when-title">{{ __("When a document changes") }}</p>
			<ul v-if="triggers.length" class="trigger-list">
				<li v-for="t in triggers" :key="t.name" class="s-row">
					<span class="when-line">{{ describeTrigger(t) }}</span>
					<span class="badge" :class="{ on: Number(t.enabled) === 1 }">{{
						Number(t.enabled) === 1 ? __("on") : __("off")
					}}</span>
				</li>
			</ul>
			<button type="button" class="s-link" data-test="triggers-open" @click="$emit('open-triggers')">
				{{ triggers.length ? __("Edit document events") : __("Add a document event") }}
			</button>
		</section>

		<p class="s-hint">
			{{ isLive ? __("Changes apply straight away.") : __("Nothing runs until you Activate.") }}
			{{ __("You can also run it by hand any time with Run.") }}
		</p>
	</div>
</template>

<script setup>
import { computed, ref } from "vue";
import { __ } from "@/utils/i18n";
import SchedulePicker from "./SchedulePicker.vue";
import { describeSchedule, proposedTimezone } from "../scheduleWords";
import { describeTrigger, scheduleEnabledOnSave } from "../setupChecklist";

const props = defineProps({
	schedule: { type: Object, required: true },
	triggers: { type: Array, default: () => [] },
	status: { type: String, default: "Draft" },
	browserZone: { type: String, default: () => Intl.DateTimeFormat().resolvedOptions().timeZone },
	saving: { type: Boolean, default: false },
});
const emit = defineEmits(["save-schedule", "open-triggers"]);

// A brand-new agent has neither: open the picker so the first step is visible.
const editingSchedule = ref(!props.schedule.cron && !props.triggers.length);
const initialTimezone = computed(() => proposedTimezone(props.schedule, props.browserZone));
const isLive = computed(() => props.status === "Active");

function onSave(config) {
	emit("save-schedule", {
		...config,
		enabled: scheduleEnabledOnSave({ wasEnabled: props.schedule.enabled, status: props.status }),
	});
	editingSchedule.value = false;
}
</script>

<style scoped src="./setupControls.css"></style>
<style scoped>
.when-section {
	display: flex;
	flex-direction: column;
	gap: 0.375rem;
	padding: var(--ql-space-2);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
}
.when-title {
	font-size: 0.6875rem;
	font-weight: 600;
	text-transform: uppercase;
	letter-spacing: 0.025em;
	color: var(--ql-text-muted);
}
.when-line {
	font-size: 0.75rem;
	color: var(--ql-text);
}
.trigger-list {
	display: flex;
	flex-direction: column;
	gap: 0.25rem;
}
.badge {
	padding: 0 0.375rem;
	font-size: 0.625rem;
	font-weight: 600;
	text-transform: uppercase;
	color: var(--ql-text-muted);
	background: var(--ql-subtle);
	border-radius: 999px;
}
.badge.on {
	color: var(--ql-success);
	background: color-mix(in srgb, var(--ql-success) 14%, transparent);
}
</style>
