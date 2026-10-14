<template>
	<section class="instructions">
		<header class="instructions-header">
			<h3 class="instructions-title">{{ __("Instructions") }}</h3>
			<button
				v-if="!editing"
				class="link-btn"
				data-test="edit-instructions"
				@click="startEdit"
			>
				{{ __("Edit") }}
			</button>
		</header>

		<template v-if="editing">
			<textarea
				ref="textareaRef"
				v-model="draft"
				class="instructions-input"
				rows="6"
				:aria-label="__('Project instructions')"
				:placeholder="__('How should the assistant work in this project?')"
				@keydown.esc.stop.prevent="cancel"
			></textarea>
			<div class="instructions-footer">
				<span class="counter" :class="{ over: overLimit }">
					{{ draft.length }} / {{ INSTRUCTIONS_MAX_LENGTH }}
				</span>
				<div class="actions">
					<button class="btn-secondary" data-test="cancel-instructions" @click="cancel">
						{{ __("Cancel") }}
					</button>
					<button
						class="btn-primary"
						data-test="save-instructions"
						:disabled="overLimit || saving"
						@click="save"
					>
						{{ __("Save") }}
					</button>
				</div>
			</div>
		</template>
		<template v-else-if="modelValue">
			<p class="instructions-text" :class="{ clamped: isLong && !expanded }">{{ modelValue }}</p>
			<button v-if="isLong" class="link-btn more-btn" data-test="instructions-more" @click="expanded = !expanded">
				{{ expanded ? __("Show less") : __("Show more") }}
			</button>
		</template>
		<p v-else class="instructions-empty">
			{{ __("No instructions yet. Add how the assistant should work in this project.") }}
		</p>
	</section>
</template>

<script setup>
import { computed, nextTick, ref } from "vue";
import { __ } from "@/utils/i18n";

const INSTRUCTIONS_MAX_LENGTH = 8000;
// Past this the card clamps to CLAMP_LINES, so a long brief can't push Documents and Memory off-screen.
const CLAMP_LINES = 6;
const CLAMP_CHARS = 400;

const props = defineProps({
	modelValue: { type: String, default: "" },
	// Async persist; rejecting keeps the editor open so the draft is not lost. The caller reports the error.
	saveFn: { type: Function, required: true },
});

const editing = ref(false);
const draft = ref("");
const saving = ref(false);
const textareaRef = ref(null);
const overLimit = computed(() => draft.value.length > INSTRUCTIONS_MAX_LENGTH);
const expanded = ref(false);
const isLong = computed(() => {
	const text = props.modelValue || "";
	return text.length > CLAMP_CHARS || text.split("\n").length > CLAMP_LINES;
});

async function startEdit() {
	draft.value = props.modelValue || "";
	editing.value = true;
	await nextTick();
	textareaRef.value?.focus();
}

async function save() {
	if (overLimit.value || saving.value) return;
	if (draft.value === (props.modelValue || "")) {
		editing.value = false;
		return;
	}
	saving.value = true;
	try {
		await props.saveFn(draft.value);
		editing.value = false;
	} catch {
		// Stay open: the caller already reported the failure.
	} finally {
		saving.value = false;
	}
}

function cancel() {
	editing.value = false;
}
</script>

<style scoped>
.instructions {
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	background: var(--ql-surface);
	padding: 0.875rem 1rem;
}

.instructions-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	margin-bottom: 0.5rem;
}

.instructions-title {
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.05em;
}

.link-btn {
	font-size: 0.8125rem;
	color: var(--ql-accent);
	background: none;
	border: none;
	cursor: pointer;
}

.instructions-text {
	font-size: 0.875rem;
	color: var(--ql-text);
	white-space: pre-wrap;
	overflow-wrap: anywhere;
}

.instructions-text.clamped {
	display: -webkit-box;
	-webkit-line-clamp: 6;
	-webkit-box-orient: vertical;
	overflow: hidden;
}

.more-btn {
	margin-top: 0.375rem;
}

.instructions-empty {
	font-size: 0.875rem;
	color: var(--ql-text-muted);
}

.instructions-input {
	width: 100%;
	font: inherit;
	font-size: 0.875rem;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	padding: 0.5rem 0.625rem;
	resize: vertical;
	outline: none;
}

.instructions-input:focus {
	border-color: var(--ql-accent);
}

.instructions-footer {
	display: flex;
	align-items: center;
	justify-content: space-between;
	margin-top: 0.5rem;
}

.counter {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.counter.over {
	color: var(--ql-danger);
}

.actions {
	display: flex;
	gap: 0.5rem;
}

.btn-primary,
.btn-secondary {
	font-size: 0.8125rem;
	font-weight: 500;
	padding: 0.375rem 0.75rem;
	border-radius: 0.5rem;
	border: none;
	cursor: pointer;
}

.btn-primary {
	color: white;
	background: var(--ql-accent);
}

.btn-primary:disabled {
	opacity: 0.5;
	cursor: not-allowed;
}

.btn-secondary {
	color: var(--ql-text);
	background: var(--ql-subtle);
}
</style>
