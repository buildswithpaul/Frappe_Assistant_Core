<template>
	<div ref="root" class="answer-rating" @keydown.esc="close">
		<button
			type="button"
			class="action-btn"
			:class="{ 'is-active': reaction === 'Up' }"
			data-test="thumb-up"
			:title="__('Good answer')"
			:aria-label="__('Good answer')"
			:aria-pressed="reaction === 'Up'"
			@click="onUp"
		>
			<svg class="w-4 h-4" viewBox="0 0 24 24" :fill="reaction === 'Up' ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
				<path d="M7 11v9H4v-9h3zm0 0l4-8a2 2 0 012 2v4h5.5a2 2 0 012 2.3l-1.2 7A2 2 0 0117.3 20H7" />
			</svg>
		</button>
		<button
			type="button"
			class="action-btn"
			:class="{ 'is-active': reaction === 'Down' }"
			ref="downButton"
			data-test="thumb-down"
			:aria-expanded="open"
			:aria-controls="popoverId"
			:title="__('Bad answer')"
			:aria-label="__('Bad answer')"
			:aria-pressed="reaction === 'Down'"
			@click="onDown"
		>
			<svg class="w-4 h-4" viewBox="0 0 24 24" :fill="reaction === 'Down' ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
				<path d="M17 13V4h3v9h-3zm0 0l-4 8a2 2 0 01-2-2v-4H5.5a2 2 0 01-2-2.3l1.2-7A2 2 0 016.7 4H17" />
			</svg>
		</button>

		<div v-if="open" :id="popoverId" ref="popover" tabindex="-1" class="reasons-popover" data-test="reasons" role="dialog" :aria-label="__('What went wrong?')">
			<div class="reasons-title">{{ __("What went wrong?") }}</div>
			<div class="reasons-chips">
				<button
					v-for="r in REASONS"
					:key="r.key"
					type="button"
					class="reason-chip"
					:class="{ 'is-selected': selected.includes(r.key) }"
					:data-reason="r.key"
					:aria-pressed="selected.includes(r.key)"
					@click="toggle(r.key)"
				>
					{{ r.label }}
				</button>
			</div>
			<textarea
				v-model="comment"
				class="reasons-comment"
				data-test="comment"
				rows="2"
				:placeholder="__('Anything else? (optional)')"
			/>
			<div class="reasons-note">
				{{ __("We link this to the answer's usage record (model, time, credits), not to what you wrote.") }}
			</div>
			<button type="button" class="reasons-send" data-test="send" @click="send">{{ __("Send") }}</button>
		</div>
	</div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { useAnswerRatingStore } from "@/stores/answerRatingStore";
import { __ } from "@/utils/i18n";

const props = defineProps({
	messageId: { type: String, required: true },
});

// Stored keys are fixed; labels are display only.
const REASONS = [
	{ key: "wrong", label: __("Wrong answer") },
	{ key: "not_what_asked", label: __("Didn't do what I asked") },
	{ key: "slow", label: __("Too slow") },
	{ key: "credits", label: __("Used too many credits") },
	{ key: "other", label: __("Other") },
];

const store = useAnswerRatingStore();
const popoverId = `reasons-${props.messageId}`;
const root = ref(null);
const downButton = ref(null);
const popover = ref(null);
const open = ref(false);
const selected = ref([]);
const comment = ref("");

const reaction = computed(() => store.ratings[props.messageId]?.reaction || null);

function close() {
	if (!open.value) return;
	open.value = false;
	downButton.value?.focus();
}

function closeOnOutsideClick(event) {
	if (!root.value?.contains(event.target)) open.value = false;
}

watch(open, async (isOpen) => {
	if (isOpen) {
		document.addEventListener("mousedown", closeOnOutsideClick);
		await nextTick();
		popover.value?.focus();
	} else {
		document.removeEventListener("mousedown", closeOnOutsideClick);
	}
});

onBeforeUnmount(() => document.removeEventListener("mousedown", closeOnOutsideClick));

function onUp() {
	open.value = false;
	if (reaction.value === "Up") store.withdraw(props.messageId);
	else store.rate(props.messageId, "Up");
}

function onDown() {
	if (reaction.value === "Down") {
		open.value = false;
		store.withdraw(props.messageId);
		return;
	}
	open.value = !open.value;
}

function toggle(key) {
	selected.value = selected.value.includes(key)
		? selected.value.filter((k) => k !== key)
		: [...selected.value, key];
}

function send() {
	store.rate(props.messageId, "Down", selected.value, comment.value.trim() || null);
	close();
	selected.value = [];
	comment.value = "";
}
</script>

<style scoped>
.answer-rating {
	position: relative;
	display: flex;
	gap: 0.25rem;
}

.action-btn {
	padding: 0.375rem;
	color: var(--ql-text-muted);
	background: none;
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.action-btn:hover,
.action-btn.is-active {
	color: var(--ql-text);
	background-color: var(--ql-subtle);
}

.reasons-popover {
	position: absolute;
	top: 100%;
	left: 0;
	z-index: 20;
	width: 18rem;
	margin-top: 0.25rem;
	padding: 0.75rem;
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
	background: var(--ql-surface, var(--ql-bg));
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	box-shadow: 0 4px 16px rgb(0 0 0 / 0.12);
}

.reasons-title {
	font-size: 0.875rem;
	font-weight: 600;
	color: var(--ql-text);
}

.reasons-chips {
	display: flex;
	flex-wrap: wrap;
	gap: 0.375rem;
}

.reason-chip {
	padding: 0.25rem 0.625rem;
	font-size: 0.75rem;
	color: var(--ql-text);
	background: none;
	border: 1px solid var(--ql-border);
	border-radius: 999px;
	cursor: pointer;
}

.reason-chip.is-selected {
	background-color: var(--ql-subtle);
	border-color: var(--ql-text-muted);
}

.reasons-comment {
	width: 100%;
	padding: 0.375rem 0.5rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
	background: none;
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	resize: vertical;
}

.reasons-note {
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
}

.reasons-send {
	align-self: flex-end;
	padding: 0.25rem 0.875rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
	background-color: var(--ql-subtle);
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	cursor: pointer;
}
</style>
