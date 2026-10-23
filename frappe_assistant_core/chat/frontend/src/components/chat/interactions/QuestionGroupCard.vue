<template>
	<section ref="rootEl" class="qgroup" :aria-label="__('Questions from FACO')">
		<header class="qg-head">
			<span class="qg-title">{{ __("{0} questions", [blocks.length]) }}</span>
			<span class="qg-dots" aria-hidden="true">
				<i v-for="block in blocks" :key="block.id" class="qg-dot" :class="{ on: isAnswered(block) }" />
			</span>
		</header>

		<ol class="qg-list">
			<li
				v-for="(block, index) in blocks"
				:key="block.id"
				class="qg-item"
				:data-question-id="block.id"
				:data-interaction-id="block.id"
			>
				<div v-if="!settled && openId === block.id" class="qg-open">
					<span class="qg-num">{{ index + 1 }}</span>
					<QuestionCard
						class="qg-question"
						:block="block"
						:interaction-type="block.interactionType"
						mode="group"
						:initial-answer="block.draft ?? null"
						:submitting="locked"
						@respond="(answer) => record(block, answer)"
					/>
				</div>
				<div v-else class="qg-done">
					<span class="qg-num">{{ index + 1 }}</span>
					<span class="qg-text">
						<span class="qg-q">{{ plainQuestion(block) }}</span>
						<span v-if="isAnswered(block)" class="qg-a">{{ answerText(answerOf(block)) }}</span>
						<span v-else-if="settled" class="qg-none">{{ __("Not answered") }}</span>
					</span>
					<button
						v-if="!settled && !locked && !block.decision"
						type="button"
						class="qg-change"
						:aria-label="
							isAnswered(block)
								? __('Change the answer to: {0}', [plainQuestion(block)])
								: __('Answer: {0}', [plainQuestion(block)])
						"
						@click="open(block.id)"
					>
						{{ isAnswered(block) ? __("Change") : __("Answer") }}
					</button>
				</div>
			</li>
		</ol>

		<footer v-if="!settled" class="qg-foot">
			<span class="qg-count" aria-live="polite">
				{{ __("{0} of {1} answered", [answeredCount, blocks.length]) }}
			</span>
			<button
				ref="sendEl"
				type="button"
				class="qg-send"
				:disabled="!allAnswered || locked"
				@click="send"
			>
				{{ locked ? __("Sending…") : __("Send answers") }}
			</button>
		</footer>
	</section>
</template>

<script setup>
import { computed, nextTick, ref, watch } from "vue";
import QuestionCard from "./QuestionCard.vue";
import { answerText, plainQuestion, responsesFor } from "./questionGroup";
import { useChatStore } from "@/stores/chatStore";
import { __ } from "@/utils/i18n";

const props = defineProps({
	// Question cards FACO asked in one pause, in order (see findQuestionGroups).
	blocks: { type: Array, required: true },
	submitting: { type: Boolean, default: false },
});
const emit = defineEmits(["approve"]);

const chatStore = useChatStore();
// Answers are drafts on the cards (block.draft) until Send records them as decisions. The
// composer fills the same drafts, so a typed answer joins the card like a tapped one.
const rootEl = ref(null);
const sendEl = ref(null);

const settled = computed(() => props.blocks.every((b) => b.status !== "pending"));
// Every card carries a recorded decision once Send is pressed; a failed resume clears them.
const locked = computed(() => props.submitting || props.blocks.every((b) => b.decision));

function answerOf(block) {
	return block.draft ?? block.decision?.userResponse ?? block.userResponse;
}

function isAnswered(block) {
	const answer = answerOf(block);
	return answer !== undefined && answer !== null && answer !== "";
}

const answeredCount = computed(() => props.blocks.filter(isAnswered).length);
const allAnswered = computed(() => answeredCount.value === props.blocks.length);

const firstUnanswered = () => props.blocks.find((b) => !isAnswered(b))?.id ?? null;
const openId = ref(firstUnanswered());

function focusOpenQuestion() {
	nextTick(() => {
		const target = openId.value
			? rootEl.value?.querySelector(
					`[data-question-id="${openId.value}"] :is(button, input):not(:disabled)`,
				)
			: sendEl.value;
		target?.focus();
	});
}

function open(id) {
	openId.value = id;
	focusOpenQuestion();
}

function openNextAfter(block) {
	const index = props.blocks.indexOf(block);
	const next = [...props.blocks.slice(index + 1), ...props.blocks.slice(0, index)].find(
		(b) => !isAnswered(b),
	);
	open(next?.id ?? null);
}

function record(block, answer) {
	chatStore.setQuestionDraft(block.id, answer);
	openNextAfter(block);
}

// An answer typed in the composer can fill the open question; move on as a tap would.
watch(
	() => [openId.value, props.blocks.find((b) => b.id === openId.value)?.draft],
	([id, draft], [previousId, previousDraft]) => {
		const block = props.blocks.find((b) => b.id === id);
		if (block && id === previousId && draft != null && draft !== previousDraft) openNextAfter(block);
	},
);

function send() {
	if (!allAnswered.value || locked.value) return;
	for (const block of props.blocks) {
		if (block.decision) continue;
		emit("approve", block.id, responsesFor(block, block.draft));
	}
}
</script>

<style scoped>
.qgroup {
	margin: 8px 0;
	border-radius: var(--ql-radius-xl);
	border: 1px solid var(--ql-gold-soft);
	background: var(--ql-surface);
	overflow: hidden;
}

.qg-head {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 10px;
	padding: 10px 14px;
	background: var(--ql-gold-soft);
}

.qg-title {
	font-size: 13px;
	font-weight: 600;
	color: var(--ql-text);
}

.qg-dots {
	display: flex;
	gap: 4px;
}

.qg-dot {
	width: 7px;
	height: 7px;
	border-radius: 50%;
	background: var(--ql-text-muted);
	opacity: 0.35;
	transition: background 0.2s ease, opacity 0.2s ease;
}

.qg-dot.on {
	background: var(--ql-accent);
	opacity: 1;
}

.qg-list {
	list-style: none;
	margin: 0;
	padding: 0;
}

.qg-item + .qg-item {
	border-top: 1px solid var(--ql-subtle);
}

.qg-open,
.qg-done {
	display: flex;
	gap: 8px;
	padding: 10px 14px;
}

.qg-open {
	align-items: flex-start;
}

.qg-done {
	align-items: baseline;
	font-size: 13px;
}

/* Question and answer share a line when there is room; on a narrow widget the answer wraps
   under the question, not under the number. */
.qg-text {
	flex: 1;
	min-width: 0;
	display: flex;
	flex-wrap: wrap;
	align-items: baseline;
	column-gap: 8px;
}

.qg-num {
	flex-shrink: 0;
	min-width: 14px;
	font-size: 11px;
	font-weight: 600;
	color: var(--ql-text-muted);
	line-height: 1.9;
}

.qg-question {
	flex: 1;
	min-width: 0;
}

.qg-open :deep(.question-block) {
	margin: 0;
	padding: 0;
}

.qg-q {
	flex: 1 1 12rem;
	min-width: 0;
	color: var(--ql-text-secondary);
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.qg-a {
	font-weight: 600;
	color: var(--ql-accent);
	overflow-wrap: anywhere;
}

.qg-none {
	color: var(--ql-text-muted);
}

.qg-change {
	flex-shrink: 0;
	padding: 2px 4px;
	font-size: 12px;
	color: var(--ql-accent);
	background: none;
	border: none;
	text-decoration: underline;
	text-underline-offset: 2px;
	cursor: pointer;
}

.qg-foot {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 10px;
	padding: 10px 14px;
	background: var(--ql-subtle);
}

.qg-count {
	font-size: 12px;
	color: var(--ql-text-secondary);
}

.qg-send {
	padding: 7px 16px;
	font-size: 12px;
	font-weight: 600;
	color: #fff;
	background: var(--ql-accent);
	border: none;
	border-radius: var(--ql-radius-md);
	cursor: pointer;
	white-space: nowrap;
}

.qg-send:hover:not(:disabled) {
	background: var(--ql-accent-hover);
}

.qg-send:disabled {
	opacity: 0.4;
	cursor: not-allowed;
}
</style>
