<template>
	<div class="ql-turn group" :class="`ql-turn-${message.role}`" :data-turn-index="messageIndex">
		<!-- Avatar rail -->
		<div class="ql-turn-avatar">
			<div v-if="isUser" class="ql-user-avatar">{{ userInitial }}</div>
			<FacoRobot
				v-else
				size="md"
				:mood="message.isStreaming ? null : 'idle'"
				:static-idle="!message.isStreaming"
				show-body
				show-arms
			/>
		</div>

		<!-- Turn content -->
		<div class="ql-turn-content">
			<div class="ql-turn-label" :class="{ 'ql-turn-label-faco': !isUser }">
				{{ turnLabel(message) }}
			</div>

			<!-- File Attachments -->
			<div v-if="message.files?.length" class="message-files">
				<div v-for="file in message.files" :key="file.name" class="file-attachment">
					<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
							d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
				</svg>
					<span>{{ file.name || file.file_name }}</span>
				</div>
			</div>

			<!-- Single render path: block renderer handles both structured blocks
			     and a lone text/markdown block. -->
			<MessageBlockRenderer
				:blocks="renderBlocks"
				:message-index="messageIndex"
				:is-streaming="isStreaming"
				@toggle-block="(msgIdx, blockId) => $emit('toggleBlock', msgIdx, blockId)"
				@approve="(blockId, responses) => $emit('approve', blockId, responses)"
				@reject="(blockId, responses) => $emit('reject', blockId, responses)"
				@preview-document="(doc) => $emit('previewDocument', doc)"
			/>

			<!-- Queued indicator (compose-while-streaming) -->
			<span v-if="message.queued" class="queued-chip">
				Queued
				<button
					class="queued-remove"
					title="Remove from queue"
					aria-label="Remove queued message"
					@click="$emit('unqueue', message._queueId)"
				>
					✕
				</button>
			</span>

			<!-- Truncation Notice -->
			<div v-if="message.truncated" class="truncation-notice">
				<svg class="truncation-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
						d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
				</svg>
				<span>Response was cut short due to length limits.</span>
				<button
					v-if="isLatest"
					class="continue-btn"
					@click="$emit('continue', message.message_id)"
				>
					Continue response
				</button>
			</div>

			<!-- Message Actions (only for assistant) -->
			<div v-if="!isUser" class="message-actions">
				<button @click="copyMessage" class="action-btn" title="Copy message" aria-label="Copy message">
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
							d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
				</svg>
				</button>
				<button
					v-if="message.message_id"
					@click="$emit('pin', message.message_id)"
					class="action-btn"
					title="Pin to index"
					aria-label="Pin message to index"
				>
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
							d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-4-7 4V5z" />
					</svg>
				</button>
			</div>

			<MessageFooter :message="message" :is-user="isUser" />
		</div>
	</div>
</template>

<script setup>
import { computed, ref, onMounted } from "vue";
import { useUserStore } from "@/stores/userStore";
import MessageBlockRenderer from "./MessageBlockRenderer.vue";
import MessageFooter from "./MessageFooter.vue";
import FacoRobot from "@/components/common/FacoRobot.vue";
import { ensureHljs } from "@/utils/markdown.js";
import { turnLabel, userInitial as deriveInitial } from "./turns.js";

const props = defineProps({
	message: {
		type: Object,
		required: true,
	},
	messageIndex: {
		type: Number,
		default: 0,
	},
	isStreaming: {
		type: Boolean,
		default: false,
	},
	isLatest: {
		type: Boolean,
		default: false,
	},
});

defineEmits(["toggleBlock", "approve", "reject", "previewDocument", "continue", "pin", "unqueue"]);

const userStore = useUserStore();

// Bump on hljs load so renderBlocks re-renders with syntax highlighting
// once the chunk arrives.
const hljsReady = ref(0);
onMounted(() => {
	ensureHljs().then(() => {
		hljsReady.value++;
	});
});

const isUser = computed(() => props.message.role === "user");

const userInitial = computed(() => deriveInitial(userStore.user));

// Single render path: if the message already carries structured blocks, use
// them; otherwise synthesize a single text block from raw content so the
// block renderer (which parses rich blocks + markdown) is the ONE code path.
// Reading hljsReady creates a reactive dep so output re-runs once highlight.js
// finishes loading.
const renderBlocks = computed(() => {
	// eslint-disable-next-line no-unused-expressions
	hljsReady.value;
	if (props.message.blocks && props.message.blocks.length > 0) {
		return props.message.blocks;
	}
	const content = props.message.content || "";
	if (!content) return [];
	return [{ id: "text", type: "text", content }];
});

function copyMessage() {
	const content = props.message.content || "";
	navigator.clipboard.writeText(content);
}
</script>

<style scoped>
.ql-turn {
	display: flex;
	align-items: flex-start;
	gap: var(--ql-turn-gap);
	padding: 2px 0 18px;
	border-bottom: 1px solid var(--ql-border);
	margin-bottom: 18px;
	font-family: var(--ql-font-ui);
}

.ql-turn-avatar {
	flex-shrink: 0;
	width: var(--ql-avatar-size);
	display: flex;
	justify-content: center;
	padding-top: 2px;
}

/* Ink-initial user avatar (07-chat-rail.html) */
.ql-user-avatar {
	width: 30px;
	height: 30px;
	border-radius: 9px;
	background: var(--ql-text);
	color: var(--ql-surface);
	display: flex;
	align-items: center;
	justify-content: center;
	font-size: 12px;
	font-weight: 600;
}

.ql-turn-content {
	flex: 1;
	min-width: 0;
	padding-top: 3px;
}

/* Uppercase turn label */
.ql-turn-label {
	font-size: var(--ql-label-size);
	text-transform: uppercase;
	letter-spacing: var(--ql-label-tracking);
	color: var(--ql-text-muted);
	margin-bottom: 4px;
}

.ql-turn-label-faco {
	color: var(--ql-accent);
}

/* User prompt reads at 16px ink, assistant body 15px — applied to the
	rendered block content via deep selectors. */
.ql-turn-user .ql-turn-content :deep(p) {
	font-size: var(--ql-prompt-size);
	color: var(--ql-text);
	line-height: 1.5;
	font-weight: 500;
}

.ql-turn-assistant .ql-turn-content :deep(p) {
	font-size: var(--ql-body-size);
	color: var(--ql-text);
	line-height: var(--ql-body-leading);
}

/* ERP figures / money align on the decimal */
.ql-turn-content :deep(td),
.ql-turn-content :deep(.ql-num) {
	font-variant-numeric: tabular-nums;
	font-family: var(--ql-font-mono);
}

.message-files {
	display: flex;
	flex-wrap: wrap;
	gap: 0.5rem;
	margin-bottom: 0.5rem;
}

.file-attachment {
	display: inline-flex;
	align-items: center;
	gap: 0.375rem;
	padding: 0.25rem 0.5rem;
	background-color: var(--ql-subtle);
	border-radius: 0.375rem;
	font-size: 0.75rem;
	color: var(--ql-text-secondary);
}

.queued-chip {
	display: inline-flex;
	align-items: center;
	gap: 0.375rem;
	margin-top: 0.5rem;
	padding: 0.25rem 0.5rem;
	background-color: var(--ql-subtle);
	border-radius: 1rem;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.queued-remove {
	background: none;
	border: none;
	color: var(--ql-text-muted);
	cursor: pointer;
	font-size: 0.75rem;
	line-height: 1;
	padding: 0;
}

.queued-remove:hover {
	color: var(--ql-danger);
}

.truncation-notice {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	margin-top: 0.75rem;
	padding: 0.5rem 0.75rem;
	background-color: var(--ql-gold-soft);
	border: 1px solid var(--ql-gold-soft);
	border-radius: 0.5rem;
	font-size: 0.8125rem;
	color: var(--ql-text-secondary);
	line-height: 1.4;
}

.truncation-icon {
	flex-shrink: 0;
	width: 1rem;
	height: 1rem;
	color: var(--ql-warning);
}

.continue-btn {
	margin-left: auto;
	padding: 0.3rem 0.75rem;
	background-color: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text);
	cursor: pointer;
	transition: all 0.15s ease;
}

.continue-btn:hover {
	background-color: var(--ql-subtle);
	border-color: var(--ql-text-muted);
}

.message-actions {
	display: flex;
	gap: 0.25rem;
	margin-top: 0.5rem;
	opacity: 0;
	transition: opacity 0.15s ease;
}

.ql-turn:hover .message-actions {
	opacity: 1;
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

.action-btn:hover {
	color: var(--ql-text);
	background-color: var(--ql-subtle);
}
</style>
