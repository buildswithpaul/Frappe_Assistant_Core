<template>
	<!-- single_select (pill buttons) -->
	<div v-if="interactionType === 'single_select'" class="question-block">
		<div class="question-text" v-html="questionHtml"></div>
		<div v-if="block.description" class="question-description" v-html="descriptionHtml"></div>
		<div class="option-pills">
			<button
				v-for="option in block.options"
				:key="option"
				class="pill"
				:class="{ selected: picked === option }"
				:aria-pressed="picked === option"
				:disabled="locked"
				@click="respond(option)"
			>
				{{ option }}
			</button>
			<!-- Free-text escape hatch: none of the canned options may fit, so let
			     the user type their own answer instead of being forced to send a
			     label like "Something else — I'll type the exact dates" verbatim. -->
			<button
				class="pill pill-custom"
				:disabled="locked"
				@click="showCustom = true"
			>
				{{ __("Type a different answer") }}
			</button>
		</div>
		<div v-if="showCustom" class="text-input-row custom-input-row">
			<input
				ref="customInputEl"
				v-model="textValue"
				type="text"
				class="text-field"
				:disabled="locked"
				:placeholder="block.placeholder || __('Type your answer…')"
				@keydown.enter="!locked && textValue.trim() && respond(textValue.trim())"
			/>
			<button
				class="ql-btn ql-btn-approve"
				:disabled="!textValue.trim() || locked"
				@click="respond(textValue.trim())"
			>
				{{ sendLabel }}
			</button>
		</div>
	</div>

	<!-- multi_select (checkboxes) -->
	<div v-else-if="interactionType === 'multi_select'" class="question-block">
		<div class="question-text" v-html="questionHtml"></div>
		<div v-if="block.description" class="question-description" v-html="descriptionHtml"></div>
		<div class="multi-options">
			<label
				v-for="option in block.options"
				:key="option"
				class="multi-item"
				:class="{ selected: selectedOptions.includes(option) }"
			>
				<input
					type="checkbox"
					:value="option"
					v-model="selectedOptions"
					:disabled="locked"
					class="multi-check"
				/>
				<span>{{ option }}</span>
			</label>
		</div>
		<button
			class="ql-btn ql-btn-approve submit-btn"
			:disabled="selectedOptions.length === 0 || locked"
			@click="respond([...selectedOptions])"
		>
			{{ multiLabel }}
		</button>
	</div>

	<!-- confirm (yes/no) -->
	<div v-else-if="interactionType === 'confirm'" class="question-block">
		<div class="question-text" v-html="questionHtml"></div>
		<div v-if="block.description" class="question-description" v-html="descriptionHtml"></div>
		<div class="confirm-actions">
			<button
				:class="[mode === 'group' ? 'pill' : 'ql-btn ql-btn-reject', { selected: picked === 'no' }]"
				:aria-pressed="picked === 'no'"
				:disabled="locked"
				@click="respond('no')"
			>
				{{ __("No") }}
			</button>
			<!-- In a group, Yes and No look alike: a filled Yes would read as already chosen. -->
			<button
				:class="[mode === 'group' ? 'pill' : 'ql-btn ql-btn-approve', { selected: picked === 'yes' }]"
				:aria-pressed="picked === 'yes'"
				:disabled="locked"
				@click="respond('yes')"
			>
				{{ __("Yes") }}
			</button>
		</div>
	</div>

	<!-- text_input -->
	<div v-else-if="interactionType === 'text_input'" class="question-block">
		<div class="question-text" v-html="questionHtml"></div>
		<div v-if="block.description" class="question-description" v-html="descriptionHtml"></div>
		<div class="text-input-row">
			<input
				v-model="textValue"
				type="text"
				class="text-field"
				:disabled="locked"
				:placeholder="block.placeholder || __('Type your answer…')"
				@keydown.enter="!locked && textValue.trim() && respond(textValue.trim())"
			/>
			<button
				class="ql-btn ql-btn-approve"
				:disabled="!textValue.trim() || locked"
				@click="respond(textValue.trim())"
			>
				{{ sendLabel }}
			</button>
		</div>
	</div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from "vue";
import { renderMarkdown } from "@/utils/markdown";
import { __ } from "@/utils/i18n";

const props = defineProps({
	block: { type: Object, required: true },
	interactionType: { type: String, required: true },
	submitting: { type: Boolean, default: false },
	// "group": one question inside a QuestionGroupCard, where an answer is a draft until
	// the group is sent, so the buttons read "Done".
	mode: { type: String, default: "single" },
	// The answer to show selected when a grouped question is reopened with Change.
	initialAnswer: { type: [String, Array], default: null },
});
const emit = defineEmits(["respond"]);

// Answered (a decision is recorded) or being sent: the card takes no more input.
const locked = computed(() => props.submitting || Boolean(props.block.decision));

// The agent writes questions in markdown; renderMarkdown sanitises the HTML.
const questionHtml = computed(() => renderMarkdown(String(props.block.question ?? "")));
const descriptionHtml = computed(() => renderMarkdown(String(props.block.description ?? "")));

const startAnswer = props.initialAnswer ?? props.block.decision?.response ?? null;
const isCannedOption = (answer) => (props.block.options || []).includes(answer);

// The answer the user picked stays marked, so a locked card still shows what was chosen.
const picked = ref(typeof startAnswer === "string" ? startAnswer : null);
const selectedOptions = ref(Array.isArray(startAnswer) ? [...startAnswer] : []);
const textValue = ref(typeof startAnswer === "string" && !isCannedOption(startAnswer) ? startAnswer : "");

const sendLabel = computed(() => (props.mode === "group" ? __("Done") : __("Send")));
const multiLabel = computed(() => {
	if (props.mode === "group") return __("Done");
	const count = selectedOptions.value.length;
	return count ? __("Submit ({0})", [count]) : __("Submit");
});

function respond(answer) {
	picked.value = typeof answer === "string" ? answer : null;
	emit("respond", answer);
}

// single_select free-text escape hatch, open when the answer being changed was typed.
const showCustom = ref(
	props.interactionType === "single_select" && typeof startAnswer === "string" && !isCannedOption(startAnswer),
);
const customInputEl = ref(null);
watch(showCustom, (open) => {
	if (open) nextTick(() => customInputEl.value?.focus());
});
</script>

<style scoped>
.question-block {
	margin: 6px 0;
	padding: 4px 0;
}

.question-text {
	font-size: 15px;
	font-weight: 500;
	color: var(--ql-text);
	line-height: 1.5;
	margin-bottom: 4px;
}

.question-text :deep(p),
.question-description :deep(p) {
	margin: 0;
}

.question-text :deep(p + p),
.question-description :deep(p + p) {
	margin-top: 6px;
}

.question-description {
	font-size: 13px;
	color: var(--ql-text-secondary);
	margin-bottom: 10px;
	line-height: 1.5;
}

/* single_select pills — teal outline */
.option-pills {
	display: flex;
	flex-wrap: wrap;
	gap: 6px;
	margin-top: 8px;
}

.pill {
	padding: 7px 16px;
	border-radius: 20px;
	font-size: 13px;
	font-weight: 500;
	background: transparent;
	color: var(--ql-accent);
	border: 1px solid var(--ql-accent-soft);
	cursor: pointer;
	transition: all 0.15s ease;
	line-height: 1.3;
}

.pill:hover {
	background: var(--ql-accent-soft);
	border-color: var(--ql-accent);
}

.pill:active {
	transform: scale(0.97);
}

/* The picked answer stays filled, including while the card is locked. */
.pill.selected,
.pill.selected:disabled {
	background: var(--ql-accent);
	border-color: var(--ql-accent);
	color: #fff;
	opacity: 1;
}

.pill.selected::before {
	content: "✓ ";
}

.pill:disabled:not(.selected) {
	opacity: 0.45;
	cursor: default;
}

/* Secondary affordance — dashed outline marks it as "write your own" rather
   than a canned option. */
.pill-custom {
	border-style: dashed;
	color: var(--ql-text-secondary);
}

.pill-custom:hover {
	color: var(--ql-accent);
}

.custom-input-row {
	margin-top: 8px;
}

/* multi_select */
.multi-options {
	display: flex;
	flex-direction: column;
	gap: 2px;
	margin-top: 6px;
}

.multi-item {
	display: flex;
	align-items: center;
	gap: 8px;
	padding: 6px 8px;
	border-radius: 6px;
	cursor: pointer;
	font-size: 13px;
	color: var(--ql-text);
	transition: background 0.1s ease;
}

.multi-item:hover {
	background: var(--ql-subtle);
}

.multi-item.selected {
	background: var(--ql-accent-soft);
}

.multi-check {
	width: 16px;
	height: 16px;
	accent-color: var(--ql-accent);
	cursor: pointer;
}

.submit-btn {
	margin-top: 10px;
	align-self: flex-start;
}

.confirm-actions {
	display: flex;
	gap: 8px;
	margin-top: 8px;
}

.text-input-row {
	display: flex;
	gap: 6px;
	margin-top: 8px;
}

.text-field {
	flex: 1;
	padding: 7px 12px;
	border-radius: 8px;
	border: 1px solid var(--ql-border);
	font-size: 13px;
	color: var(--ql-text);
	background: var(--ql-surface);
	outline: none;
	transition: border-color 0.15s ease;
}

.text-field:focus {
	border-color: var(--ql-accent);
}

.text-field::placeholder {
	color: var(--ql-text-muted);
}

/* Shared ql buttons (scoped — duplicated from ApprovalCard) */
.ql-btn {
	font-size: 12px;
	font-weight: 500;
	border-radius: 8px;
	cursor: pointer;
	transition: all 0.15s ease;
	white-space: nowrap;
}

.ql-btn:disabled {
	opacity: 0.4;
	cursor: not-allowed;
}

.ql-btn.selected:disabled {
	opacity: 1;
	box-shadow: 0 0 0 2px var(--ql-accent-soft);
}

.ql-btn-approve {
	font-weight: 600;
	padding: 7px 16px;
	background: var(--ql-accent);
	color: #fff;
	border: none;
}

.ql-btn-approve:hover:not(:disabled) {
	background: var(--ql-accent-hover);
}

.ql-btn-reject {
	padding: 7px 14px;
	background: var(--ql-surface);
	color: var(--ql-text-secondary);
	border: 1px solid var(--ql-border);
}

.ql-btn-reject:hover:not(:disabled) {
	color: var(--ql-danger);
	border-color: var(--ql-danger);
}
</style>
