<template>
	<div class="ticket-detail">
		<button class="back-btn" @click="$emit('back')">
			<svg
				width="14"
				height="14"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
			>
				<path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7" />
			</svg>
			Back to tickets
		</button>

		<header class="detail-header">
			<div class="header-top">
				<h3 class="detail-subject">{{ ticket.subject }}</h3>
				<TicketStatusPill :status="ticket.status" />
				<button
					class="refresh-btn"
					:disabled="refreshing"
					aria-label="Refresh"
					@click="$emit('refresh')"
				>
					<svg
						width="14"
						height="14"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
						:class="{ spinning: refreshing }"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M4 4v5h5M20 20v-5h-5M5.5 9a7 7 0 0111.9-2.5L20 9M18.5 15a7 7 0 01-11.9 2.5L4 15"
						/>
					</svg>
					{{ refreshing ? "Refreshing…" : "Refresh" }}
				</button>
			</div>
			<span class="detail-meta">Opened {{ formatDate(ticket.creation) }}</span>
		</header>

		<div class="thread">
			<div
				v-for="m in ticket.messages"
				:key="m.name"
				class="bubble"
				:class="isUser(m) ? 'from-user' : 'from-support'"
			>
				<div class="bubble-meta">
					<span class="bubble-author">{{ isUser(m) ? "You" : "Support" }}</span>
					<span class="bubble-date">{{ formatDate(m.creation) }}</span>
				</div>
				<div class="bubble-body" v-html="renderContent(m.content)"></div>
			</div>
		</div>

		<div v-if="ticket.status === 'Closed'" class="closed-note">
			This ticket is closed.
		</div>

		<div v-else class="reply-box" @paste="attachments.handlePaste">
			<textarea
				v-model="reply"
				class="reply-input"
				rows="3"
				placeholder="Write a reply…"
				:disabled="submitting"
			></textarea>
			<AttachmentPicker
				:files="attachments.files.value"
				:disabled="submitting"
				@add="attachments.addFiles"
				@remove="attachments.removeFile"
				@retry="attachments.retryFile"
			/>
			<div class="reply-actions">
				<button
					class="send-btn"
					:disabled="submitting || !reply.trim()"
					@click="send"
				>
					{{ submitting ? "Sending…" : "Send reply" }}
				</button>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref } from "vue";
import DOMPurify from "dompurify";
import TicketStatusPill from "./TicketStatusPill.vue";
import AttachmentPicker from "@/components/support/support/AttachmentPicker.vue";
import { useTicketAttachments } from "@/composables/useTicketAttachments.js";

const props = defineProps({
	ticket: { type: Object, default: () => ({ messages: [] }) },
	submitting: { type: Boolean, default: false },
	refreshing: { type: Boolean, default: false },
});

const emit = defineEmits(["back", "reply", "refresh"]);

const reply = ref("");
const attachments = useTicketAttachments();

function isUser(m) {
	return m.sent_or_received === "Received";
}

// Explicit img/a allowlist so inline attachment media survives sanitization
// even if DOMPurify's default profile changes upstream.
function renderContent(html) {
	return DOMPurify.sanitize(html || "", {
		ADD_TAGS: ["img", "a"],
		ADD_ATTR: ["src", "href", "target", "rel"],
	});
}

function formatDate(value) {
	if (!value) return "";
	return new Date(value).toLocaleDateString();
}

function send() {
	const text = reply.value.trim();
	if (!text || props.submitting) return;
	emit("reply", { text, attachmentIds: attachments.consumeAttachmentIds() });
	reply.value = "";
}

defineExpose({ renderContent });
</script>

<style scoped>
.ticket-detail {
	display: flex;
	flex-direction: column;
	gap: 1rem;
}

.back-btn {
	display: inline-flex;
	align-items: center;
	gap: 0.35rem;
	align-self: flex-start;
	padding: 0.3rem 0.5rem;
	font-size: 0.8rem;
	color: var(--ql-text-muted, #64748b);
	background: transparent;
	border: none;
	cursor: pointer;
}

.back-btn:hover {
	color: var(--ql-text, #1e293b);
}

.detail-header {
	display: flex;
	flex-direction: column;
	gap: 0.35rem;
	padding-bottom: 0.75rem;
	border-bottom: 1px solid var(--ql-border, #e2e8f0);
}

.header-top {
	display: flex;
	align-items: center;
	gap: 0.6rem;
}

.refresh-btn {
	display: inline-flex;
	align-items: center;
	gap: 0.35rem;
	margin-left: auto;
	padding: 0.3rem 0.5rem;
	font-size: 0.8rem;
	color: var(--ql-text-muted, #64748b);
	background: transparent;
	border: none;
	cursor: pointer;
}

.refresh-btn:hover:not(:disabled) {
	color: var(--ql-text, #1e293b);
}

.refresh-btn:disabled {
	opacity: 0.5;
	cursor: not-allowed;
}

.refresh-btn .spinning {
	animation: refresh-spin 0.8s linear infinite;
}

@keyframes refresh-spin {
	to {
		transform: rotate(360deg);
	}
}

.detail-subject {
	margin: 0;
	font-size: 1.05rem;
	font-weight: 600;
	color: var(--ql-text, #1e293b);
}

.detail-meta {
	font-size: 0.78rem;
	color: var(--ql-text-muted, #94a3b8);
}

.thread {
	display: flex;
	flex-direction: column;
	gap: 0.75rem;
}

.bubble {
	padding: 0.7rem 0.9rem;
	border-radius: 10px;
	max-width: 85%;
}

.bubble.from-user {
	align-self: flex-end;
	background: var(--ql-accent-soft);
	border: 1px solid var(--ql-border);
}

.bubble.from-support {
	align-self: flex-start;
	background: var(--ql-subtle);
	border: 1px solid var(--ql-border);
}

.bubble-meta {
	display: flex;
	align-items: baseline;
	justify-content: space-between;
	gap: 1rem;
	margin-bottom: 0.3rem;
}

.bubble-author {
	font-size: 0.78rem;
	font-weight: 600;
	color: var(--ql-text, #1e293b);
}

.bubble-date {
	font-size: 0.72rem;
	color: var(--ql-text-muted, #94a3b8);
}

.bubble-body {
	font-size: 0.875rem;
	line-height: 1.6;
	color: var(--ql-text, #1e293b);
	word-break: break-word;
}

.bubble-body :deep(p) {
	margin: 0.3rem 0;
}

.bubble-body :deep(img) {
	display: block;
	max-width: 100%;
	max-height: 320px;
	border-radius: 8px;
	border: 1px solid var(--ql-border);
	margin: 0.4rem 0;
	cursor: pointer;
}

.bubble-body :deep(a) {
	color: var(--ql-accent);
	text-decoration: underline;
}

.closed-note {
	font-size: 0.82rem;
	color: var(--ql-text-muted, #64748b);
	text-align: center;
	padding: 0.75rem;
	border: 1px dashed var(--ql-border, #e2e8f0);
	border-radius: 8px;
}

.reply-box {
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
	padding-top: 0.5rem;
	border-top: 1px solid var(--ql-border, #e2e8f0);
}

.reply-input {
	width: 100%;
	resize: vertical;
	font: inherit;
	font-size: 0.875rem;
	padding: 0.6rem 0.75rem;
	border: 1px solid var(--ql-border, #e2e8f0);
	border-radius: 8px;
	background: var(--ql-surface, #fff);
	color: var(--ql-text, #1e293b);
	box-sizing: border-box;
}

.reply-input:focus {
	outline: none;
	border-color: var(--ql-accent, #6366f1);
}

.reply-actions {
	display: flex;
	justify-content: flex-end;
}

.send-btn {
	padding: 0.45rem 1rem;
	font-size: 0.85rem;
	font-weight: 600;
	color: #fff;
	background: var(--ql-accent, #6366f1);
	border: none;
	border-radius: 8px;
	cursor: pointer;
	transition: opacity 0.15s ease;
}

.send-btn:disabled {
	opacity: 0.5;
	cursor: not-allowed;
}
</style>
