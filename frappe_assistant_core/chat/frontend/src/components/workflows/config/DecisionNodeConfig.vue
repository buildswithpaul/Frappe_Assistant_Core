<template>
	<div class="decision-config">
		<div class="config-section">
			<div class="field-header">
				<label class="config-label" :for="questionId">{{ __("Question") }}</label>
				<VariableInserter
					v-if="!readonly"
					:global-variables="variables"
					@insert="insertVariable"
				/>
			</div>
			<textarea
				:id="questionId"
				ref="questionRef"
				data-test="decision-question"
				class="config-input config-textarea"
				rows="4"
				:value="config.question"
				:placeholder="__('e.g. Is this customer asking for a refund?')"
				:readonly="readonly"
				@input="setQuestion($event.target.value)"
			></textarea>
			<p v-if="problems.question" class="config-hint error" role="alert">
				{{ problems.question }}
			</p>
			<p class="config-hint">
				{{ questionHint }}
				<span class="count">{{ questionLength }} / {{ limits.questionMaxLength }}</span>
			</p>
		</div>

		<div class="config-section">
			<span class="config-label">{{ __("Choices") }}</span>
			<div v-for="(choice, i) in choices" :key="i" class="choice-row">
				<input
					data-test="decision-choice-input"
					class="config-input"
					:value="choice"
					:aria-label="__('Choice {0}', [i + 1])"
					:readonly="readonly"
					@input="setChoice(i, $event.target.value)"
					@change="setChoice(i, $event.target.value.trim())"
				/>
				<button
					v-if="!readonly"
					type="button"
					data-test="decision-remove-choice"
					class="remove-btn"
					:disabled="choices.length <= limits.minChoices"
					:title="__('Remove choice')"
					:aria-label="__('Remove choice {0}', [i + 1])"
					@click="removeChoice(i)"
				>
					&times;
				</button>
				<p v-if="problems.choices[i]" class="config-hint error choice-error" role="alert">
					{{ problems.choices[i] }}
				</p>
			</div>
			<p v-if="problems.list" class="config-hint error" role="alert">{{ problems.list }}</p>
			<button
				v-if="!readonly && choices.length < limits.maxChoices"
				type="button"
				data-test="decision-add-choice"
				class="link-btn"
				@click="addChoice"
			>
				{{ __("Add choice") }}
			</button>
		</div>

		<div class="config-info">
			<p>
				{{
					__(
						"Each choice is a branch: drag from its dot on the step to the step that should run next."
					)
				}}
			</p>
			<p>
				{{
					__(
						"AI answers the question about this step's input and follows one choice. The input passes on unchanged. It uses credits like a Task step."
					)
				}}
			</p>
			<p>
				{{ __("Renaming or removing a choice disconnects its branch; draw it again.") }}
			</p>
		</div>
	</div>
</template>

<script setup>
import { ref, computed, useId } from "vue";
import { __ } from "@/utils/i18n";
import VariableInserter from "./VariableInserter.vue";
import { spliceAtCaret } from "./spliceAtCaret";
import { DECISION_LIMITS, decisionConfigProblems } from "../graphUtils";

const props = defineProps({
	config: { type: Object, required: true },
	/** Workflow-level global_settings.variables — offered by the inserter. */
	variables: { type: Object, default: () => ({}) },
	readonly: { type: Boolean, default: false },
});
const emit = defineEmits(["update"]);

const limits = DECISION_LIMITS;
const questionId = useId();
const questionRef = ref(null);

// Literal braces would be read as interpolation inside the template.
const questionHint = __("Can use {0} and your variables.", ["{{ input }}"]);

const choices = computed(() => (Array.isArray(props.config.choices) ? props.config.choices : []));
const questionLength = computed(() => String(props.config.question || "").length);
const problems = computed(() => decisionConfigProblems(props.config));

function emitUpdate() {
	emit("update", { config: { ...props.config, choices: [...choices.value] } });
}

function setQuestion(value) {
	if (props.readonly) return;
	props.config.question = value;
	emitUpdate();
}

function insertVariable(placeholder) {
	setQuestion(spliceAtCaret(props.config.question || "", placeholder, questionRef.value));
}

function setChoice(index, value) {
	if (props.readonly) return;
	const next = [...choices.value];
	next[index] = value;
	props.config.choices = next;
	emitUpdate();
}

function addChoice() {
	if (props.readonly || choices.value.length >= limits.maxChoices) return;
	props.config.choices = [...choices.value, ""];
	emitUpdate();
}

function removeChoice(index) {
	if (props.readonly || choices.value.length <= limits.minChoices) return;
	props.config.choices = choices.value.filter((_, i) => i !== index);
	emitUpdate();
}
</script>

<style scoped src="./nodeConfigFields.css"></style>
<style scoped>
.field-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	margin-bottom: 0.375rem;
}
.field-header .config-label {
	margin-bottom: 0;
}
.count {
	float: right;
}
.choice-row {
	display: grid;
	grid-template-columns: 1fr auto;
	gap: 0.375rem;
	align-items: center;
	margin-bottom: 0.375rem;
}
.choice-error {
	grid-column: 1 / -1;
	margin-top: 0;
}
.remove-btn {
	width: 1.75rem;
	height: 1.75rem;
	padding: 0;
	font-size: 1rem;
	line-height: 1;
	color: var(--ql-text-muted);
	background: transparent;
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	cursor: pointer;
}
.remove-btn:hover:not(:disabled) {
	color: var(--ql-danger);
	border-color: var(--ql-danger);
}
.remove-btn:disabled {
	opacity: 0.4;
	cursor: not-allowed;
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
.config-info {
	background: var(--ql-subtle);
	border-radius: 0.375rem;
	padding: 0.625rem 0.75rem;
	margin-top: 0.75rem;
}
.config-info p {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	margin: 0;
	line-height: 1.5;
}
.config-info p + p {
	margin-top: 0.25rem;
}
</style>
