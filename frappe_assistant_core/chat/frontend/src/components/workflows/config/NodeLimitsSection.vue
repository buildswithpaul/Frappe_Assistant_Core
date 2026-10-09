<template>
	<div class="config-section">
		<span class="config-label">{{ __("Limits") }}</span>
		<div class="limit-row">
			<label class="limit-label" :for="callsId">{{ __("Max tool calls") }}</label>
			<input
				:id="callsId"
				data-test="limit-tool-calls"
				type="number"
				:min="callLimits.min"
				:max="callLimits.max"
				class="config-input limit-input"
				:value="config.max_tool_calls ?? callLimits.default"
				:readonly="readonly"
				@change="setToolCalls($event.target.value)"
			/>
		</div>
		<div v-if="showTimeout" class="limit-row">
			<label class="limit-label" :for="timeoutId">{{ __("Timeout (seconds)") }}</label>
			<input
				:id="timeoutId"
				data-test="limit-timeout"
				type="number"
				:min="timeoutLimits.min"
				:max="timeoutLimits.max"
				class="config-input limit-input"
				:placeholder="__('Workflow default')"
				:value="config.timeout_seconds ?? ''"
				:readonly="readonly"
				@change="setTimeoutSeconds($event.target.value)"
			/>
		</div>
		<p class="config-hint">
			{{ __("The task stops calling tools after this many calls and reports what it has.") }}
		</p>
	</div>
</template>

<script setup>
import { useId } from "vue";
import { __ } from "@/utils/i18n";
import { NODE_LIMITS, clampInt } from "../graphUtils";

const props = defineProps({
	config: { type: Object, required: true },
	showTimeout: { type: Boolean, default: true },
	readonly: { type: Boolean, default: false },
});
const emit = defineEmits(["update"]);

const callLimits = NODE_LIMITS.agent.max_tool_calls;
const timeoutLimits = NODE_LIMITS.agent.timeout_seconds;
const callsId = useId();
const timeoutId = useId();

function emitUpdate() {
	emit("update", { config: { ...props.config } });
}

function setToolCalls(value) {
	if (props.readonly) return;
	props.config.max_tool_calls = clampInt(value, callLimits);
	emitUpdate();
}

// Blank means "the workflow's timeout": the key is removed, never saved as 0.
function setTimeoutSeconds(value) {
	if (props.readonly) return;
	const seconds = clampInt(value, timeoutLimits);
	if (seconds === undefined) delete props.config.timeout_seconds;
	else props.config.timeout_seconds = seconds;
	emitUpdate();
}
</script>

<style scoped src="./nodeConfigFields.css"></style>
<style scoped>
.limit-row {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 0.5rem;
	margin-bottom: 0.375rem;
}
.limit-label {
	font-size: 0.8125rem;
	color: var(--ql-text);
}
.limit-input {
	width: 7rem;
}
</style>
