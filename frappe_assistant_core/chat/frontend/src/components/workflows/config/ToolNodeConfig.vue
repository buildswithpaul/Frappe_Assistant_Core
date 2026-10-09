<template>
	<div class="tool-config">
		<div class="config-section">
			<span class="config-label">{{ __("Tool") }}</span>
			<div v-if="config.tool_name" class="chosen-tool">
				<code class="mono">{{ config.tool_name }}</code>
				<span v-if="config.server" class="chosen-server">{{ config.server }}</span>
			</div>
			<button
				v-if="!readonly"
				type="button"
				data-test="choose-tool"
				class="link-btn"
				@click="showPicker = !showPicker"
			>
				{{ config.tool_name ? __("Change tool") : __("Choose tool") }}
			</button>
			<ToolPicker
				v-if="showPicker"
				v-model="showPicker"
				:all-tools="allTools"
				:selected-tool-keys="selectedKeys"
				:is-loading="isLoadingTools"
				@select="pick"
			/>
		</div>

		<div class="config-section">
			<label class="config-label" :for="argsId">{{ __("Arguments (JSON)") }}</label>
			<textarea
				:id="argsId"
				data-test="tool-arguments"
				class="config-input config-textarea mono"
				rows="7"
				:value="argsText"
				:readonly="readonly"
				@input="onArgs($event.target.value)"
			></textarea>
			<p v-if="argsError" class="config-hint error" role="alert">{{ argsError }}</p>
			<p v-if="hints.names.length" class="config-hint">
				{{ __("This tool takes:") }}
				<code v-for="name in hints.names" :key="name" class="arg-name mono">
					{{ name }}<span v-if="hints.required.includes(name)">*</span>
				</code>
			</p>
			<p class="config-hint">{{ templateHint }}</p>
		</div>

		<div class="config-row">
			<div class="config-section">
				<label class="config-label" :for="rowsId">{{ __("Max rows") }}</label>
				<input
					:id="rowsId"
					data-test="tool-max-rows"
					type="number"
					:min="rowLimits.min"
					:max="rowLimits.max"
					class="config-input"
					:value="config.max_rows ?? rowLimits.default"
					:readonly="readonly"
					@change="setMaxRows($event.target.value)"
				/>
			</div>
			<div class="config-section">
				<label class="config-label" :for="outputId">{{ __("Output") }}</label>
				<select
					:id="outputId"
					class="config-input"
					:value="config.output || 'table'"
					:disabled="readonly"
					@change="setOutput($event.target.value)"
				>
					<option value="table">{{ __("Table (rows + columns)") }}</option>
					<option value="json">{{ __("Raw JSON") }}</option>
				</select>
			</div>
		</div>

		<p class="config-hint">
			{{
				__(
					"Runs without AI and costs no credits. A write tool needs “Always allow” for {0}, or unattended runs skip it.",
					[runtimeUserLabel || __("this agent's user")]
				)
			}}
		</p>
	</div>
</template>

<script setup>
import { ref, computed, watch, useId } from "vue";
import { __ } from "@/utils/i18n";
import ToolPicker from "./ToolPicker.vue";
import { bareToolName, toolKey } from "./toolDirectives";
import { parseArguments, argumentHints } from "./toolNodeConfig";
import { NODE_LIMITS, clampInt } from "../graphUtils";

const props = defineProps({
	config: { type: Object, required: true },
	allTools: { type: Array, default: () => [] },
	isLoadingTools: { type: Boolean, default: false },
	runtimeUserLabel: { type: String, default: "" },
	readonly: { type: Boolean, default: false },
});
const emit = defineEmits(["update"]);

const rowLimits = NODE_LIMITS.tool.max_rows;
const argsId = useId();
const rowsId = useId();
const outputId = useId();

// Literal braces would be read as interpolation inside the template.
const templateHint = __(
	"Text values can use {0}, {1}, {2} and your variables.",
	["{{ input }}", "{{ today }}", "{{ now }}"]
);

const showPicker = ref(false);
const argsText = ref(JSON.stringify(props.config.arguments || {}, null, 2));
const argsError = ref("");

// Resync when the arguments change from outside the textarea, but never while
// the user's text is unparseable or already means the same value (no reformatting
// mid-typing).
watch(
	() => props.config.arguments,
	(value) => {
		if (argsError.value) return;
		const typed = parseArguments(argsText.value);
		if (typed.ok && JSON.stringify(typed.value) === JSON.stringify(value || {})) return;
		argsText.value = JSON.stringify(value || {}, null, 2);
	}
);

const selectedKeys = computed(
	() =>
		new Set(
			props.config.tool_name
				? [toolKey({ original_name: props.config.tool_name, server: props.config.server })]
				: []
		)
);
const pickedTool = computed(() =>
	props.allTools.find(
		(t) =>
			bareToolName(t) === props.config.tool_name &&
			(!props.config.server || t.server === props.config.server)
	)
);
const hints = computed(() => argumentHints(pickedTool.value));

function emitUpdate() {
	emit("update", { config: { ...props.config } });
}

function pick(tool) {
	if (props.readonly) return;
	props.config.tool_name = bareToolName(tool);
	props.config.server = tool.server || "";
	showPicker.value = false;
	emitUpdate();
}

function onArgs(text) {
	if (props.readonly) return;
	argsText.value = text;
	const parsed = parseArguments(text);
	if (!parsed.ok) {
		argsError.value = parsed.error;
		return;
	}
	argsError.value = "";
	props.config.arguments = parsed.value;
	emitUpdate();
}

function setMaxRows(value) {
	if (props.readonly) return;
	props.config.max_rows = clampInt(value, rowLimits);
	emitUpdate();
}

function setOutput(value) {
	if (props.readonly) return;
	props.config.output = value === "json" ? "json" : "table";
	emitUpdate();
}
</script>

<style scoped src="./nodeConfigFields.css"></style>
<style scoped>
.config-row {
	display: grid;
	grid-template-columns: 1fr 1fr;
	gap: 0.5rem;
}
.chosen-tool {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	margin-bottom: 0.375rem;
	font-size: 0.8125rem;
}
.chosen-server {
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
}
.arg-name {
	margin-left: 0.25rem;
}
.link-btn {
	padding: 0;
	background: none;
	border: none;
	font-size: 0.75rem;
	color: var(--ql-accent);
	cursor: pointer;
}
.link-btn:hover {
	text-decoration: underline;
}
</style>
