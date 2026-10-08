<template>
	<div class="loop-config">
		<div class="config-section">
			<label class="config-label" :for="pathId">{{ __("Items from") }}</label>
			<input
				:id="pathId"
				data-test="loop-items-path"
				class="config-input mono"
				:value="config.items_path ?? 'rows'"
				:readonly="readonly"
				@change="setPath($event.target.value)"
			/>
			<p class="config-hint">
				{{
					__(
						"Dotted path into the previous step's JSON. A Tool step's table output lists its rows under rows."
					)
				}}
			</p>
		</div>

		<div class="config-grid">
			<template v-for="field in numberFields" :key="field.key">
				<label class="grid-label" :for="field.id">{{ field.label }}</label>
				<input
					:id="field.id"
					:data-test="field.test"
					type="number"
					:min="field.limits.min"
					:max="field.limits.max"
					class="config-input"
					:value="config[field.key] ?? field.limits.default"
					:readonly="readonly"
					@change="setNumber(field.key, $event.target.value)"
				/>
			</template>
		</div>
		<p class="config-hint">{{ __("Each item runs a fresh task and is billed on its own.") }}</p>

		<h4 class="section-heading">{{ __("For each item") }}</h4>
		<AgentConfig
			node-kind="loop"
			:config="config"
			:node-id="nodeId"
			:models="models"
			:models-error="modelsError"
			:all-tools="allTools"
			:tools-result="toolsResult"
			:is-loading-tools="isLoadingTools"
			:variables="variables"
			:runtime-user-label="runtimeUserLabel"
			:runtime-user="runtimeUser"
			:readonly="readonly"
			@update="(data) => emit('update', data)"
			@reload-tools="emit('reload-tools')"
		/>
	</div>
</template>

<script setup>
import { useId } from "vue";
import { __ } from "@/utils/i18n";
import AgentConfig from "../AgentConfig.vue";
import { NODE_LIMITS, clampInt } from "../graphUtils";

const props = defineProps({
	config: { type: Object, required: true },
	nodeId: { type: String, default: "" },
	models: { type: Array, default: () => [] },
	modelsError: { type: String, default: "" },
	allTools: { type: Array, default: () => [] },
	toolsResult: { type: Object, default: null },
	isLoadingTools: { type: Boolean, default: false },
	variables: { type: Object, default: () => ({}) },
	runtimeUserLabel: { type: String, default: "this agent's user" },
	/** Whose tools to preview; null when the viewer may not name one. */
	runtimeUser: { type: String, default: null },
	readonly: { type: Boolean, default: false },
});
const emit = defineEmits(["update", "reload-tools"]);

const pathId = useId();
const numberFields = [
	{ key: "max_items", label: __("Max items"), test: "loop-max-items" },
	{ key: "concurrency", label: __("At the same time"), test: "loop-concurrency" },
	{ key: "stop_after_failures", label: __("Stop after failures"), test: "loop-stop-after" },
].map((field) => ({ ...field, id: useId(), limits: NODE_LIMITS.loop[field.key] }));

function emitUpdate() {
	emit("update", { config: { ...props.config } });
}

function setPath(value) {
	if (props.readonly) return;
	props.config.items_path = value.trim() || "rows";
	emitUpdate();
}

function setNumber(key, value) {
	if (props.readonly) return;
	props.config[key] = clampInt(value, NODE_LIMITS.loop[key]);
	emitUpdate();
}
</script>

<style scoped src="./nodeConfigFields.css"></style>
<style scoped>
.config-grid {
	display: grid;
	grid-template-columns: 1fr 6rem;
	gap: 0.375rem 0.5rem;
	align-items: center;
}
.grid-label {
	font-size: 0.8125rem;
	color: var(--ql-text);
}
.section-heading {
	margin: 1rem 0 0.5rem;
	font-size: 0.8125rem;
	font-weight: 600;
	color: var(--ql-text);
}
</style>
