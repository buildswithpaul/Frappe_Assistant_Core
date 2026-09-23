<template>
	<!-- single_select (pill buttons) -->
	<div v-if="interactionType === 'single_select'" class="question-block">
		<div class="question-text">{{ block.question }}</div>
		<div v-if="block.description" class="question-description">{{ block.description }}</div>
		<div class="option-pills">
			<button
				v-for="option in block.options"
				:key="option"
				class="pill"
				:disabled="submitting"
				@click="emit('respond', option)"
			>
				{{ option }}
			</button>
			<!-- Free-text escape hatch: none of the canned options may fit, so let
			     the user type their own answer instead of being forced to send a
			     label like "Something else — I'll type the exact dates" verbatim. -->
			<button
				class="pill pill-custom"
				:disabled="submitting"
				@click="showCustom = true"
			>
				Type a different answer
			</button>
		</div>
		<div v-if="showCustom" class="text-input-row custom-input-row">
			<input
				ref="customInputEl"
				v-model="textValue"
				type="text"
				class="text-field"
				:disabled="submitting"
				:placeholder="block.placeholder || 'Type your answer…'"
				@keydown.enter="!submitting && textValue.trim() && emit('respond', textValue.trim())"
			/>
			<button
				class="ql-btn ql-btn-approve"
				:disabled="!textValue.trim() || submitting"
				@click="emit('respond', textValue.trim())"
			>
				Send
			</button>
		</div>
	</div>

	<!-- multi_select (checkboxes) -->
	<div v-else-if="interactionType === 'multi_select'" class="question-block">
		<div class="question-text">{{ block.question }}</div>
		<div v-if="block.description" class="question-description">{{ block.description }}</div>
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
					class="multi-check"
				/>
				<span>{{ option }}</span>
			</label>
		</div>
		<button
			class="ql-btn ql-btn-approve submit-btn"
			:disabled="selectedOptions.length === 0 || submitting"
			@click="emit('respond', selectedOptions)"
		>
			Submit{{ selectedOptions.length ? ` (${selectedOptions.length})` : "" }}
		</button>
	</div>

	<!-- confirm (yes/no) -->
	<div v-else-if="interactionType === 'confirm'" class="question-block">
		<div class="question-text">{{ block.question }}</div>
		<div v-if="block.description" class="question-description">{{ block.description }}</div>
		<div class="confirm-actions">
			<button class="ql-btn ql-btn-reject" :disabled="submitting" @click="emit('respond', 'no')">
				No
			</button>
			<button class="ql-btn ql-btn-approve" :disabled="submitting" @click="emit('respond', 'yes')">
				Yes
			</button>
		</div>
	</div>

	<!-- text_input -->
	<div v-else-if="interactionType === 'text_input'" class="question-block">
		<div class="question-text">{{ block.question }}</div>
		<div v-if="block.description" class="question-description">{{ block.description }}</div>
		<div class="text-input-row">
			<input
				v-model="textValue"
				type="text"
				class="text-field"
				:disabled="submitting"
				:placeholder="block.placeholder || 'Type your answer...'"
				@keydown.enter="!submitting && textValue.trim() && emit('respond', textValue.trim())"
			/>
			<button
				class="ql-btn ql-btn-approve"
				:disabled="!textValue.trim() || submitting"
				@click="emit('respond', textValue.trim())"
			>
				Send
			</button>
		</div>
	</div>
</template>

<script setup>
import { nextTick, ref, watch } from "vue";

const props = defineProps({
	block: { type: Object, required: true },
	interactionType: { type: String, required: true },
	submitting: { type: Boolean, default: false },
});
const emit = defineEmits(["respond"]);

const selectedOptions = ref([]);
const textValue = ref("");

// single_select free-text escape hatch.
const showCustom = ref(false);
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
