<template>
	<div class="drilldown">
		<!-- Header -->
		<div class="drilldown-header">
			<button class="back-btn" @click="$emit('back')">
				<svg class="back-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M15 19l-7-7 7-7"
					/>
				</svg>
				Back
			</button>
			<div class="drilldown-meta">
				<h3 class="drilldown-title">{{ conversation?.title || "Untitled" }}</h3>
				<div class="drilldown-stats">
					<span class="stat"
						>{{ formatCredits(conversation?.total_credits) }} credits</span
					>
					<span class="stat-sep">&middot;</span>
					<span class="stat">{{ conversation?.total_messages || 0 }} messages</span>
					<span class="stat-sep" v-if="conversation?.created_at">&middot;</span>
					<span class="stat" v-if="conversation?.created_at">{{
						formatDate(conversation.created_at)
					}}</span>
				</div>
			</div>
		</div>

		<!-- Loading -->
		<div v-if="loading" class="drilldown-loading">
			<div class="loading-spinner"></div>
		</div>

		<!-- Messages Timeline -->
		<div v-else-if="visibleMessages.length || hiddenContextCount" class="message-timeline">
			<!-- Collapsible summary for filtered context-injection rows. Keeps
			     the drill-down focused on what the user actually said and
			     what the assistant replied, without hiding the fact that
			     context was injected (that's load-bearing for debugging
			     unexpected memory leaks into the conversation). -->
			<div v-if="hiddenContextCount" class="context-summary">
				<button class="context-toggle" @click="showContext = !showContext">
					<svg
						class="context-chevron"
						:class="{ rotated: showContext }"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M9 5l7 7-7 7"
						/>
					</svg>
					<span>
						{{ hiddenContextCount }} context injection{{
							hiddenContextCount > 1 ? "s" : ""
						}}
						hidden
					</span>
					<span class="context-hint">{{ showContext ? "hide" : "show" }}</span>
				</button>
			</div>

			<div
				v-for="(msg, idx) in displayedMessages"
				:key="msg.message_id || idx"
				class="message-row"
				:class="{
					'is-assistant': msg.role === 'assistant',
					'is-user': msg.role === 'user',
					'is-context': msg._isContext,
				}"
			>
				<div class="msg-role">
					<div class="role-badge" :class="msg._isContext ? 'system' : msg.role">
						{{
							msg._isContext
								? "Ctx"
								: msg.role === "assistant"
								? "AI"
								: msg.role === "user"
								? "You"
								: "Sys"
						}}
					</div>
				</div>
				<div class="msg-content">
					<p class="msg-preview">{{ msg.content_preview }}</p>
					<div class="msg-meta">
						<span v-if="msg.model_id" class="msg-model">{{
							shortenModel(msg.model_id)
						}}</span>
						<button
							v-if="isDelegated(msg)"
							class="msg-badge delegated-badge"
							@click="toggleBreakdown(msg)"
							:title="'This turn used multiple models via delegation'"
						>
							<svg
								class="delegated-chevron"
								:class="{ rotated: isExpanded(msg) }"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M9 5l7 7-7 7"
								/>
							</svg>
							Delegated &middot; {{ msg.model_breakdown.length }} models
						</button>
						<span
							v-if="msg.tool_count"
							class="msg-badge tool-badge"
							:title="(msg.tool_names || []).join(', ')"
							>{{ msg.tool_count }} tool{{ msg.tool_count > 1 ? "s" : "" }}</span
						>
						<span v-if="msg.had_thinking" class="msg-badge thinking-badge"
							>thinking</span
						>
						<span v-if="msg.created_at" class="msg-time">{{
							formatTime(msg.created_at)
						}}</span>
					</div>
					<!-- Per-model breakdown for delegating turns -->
					<MessageModelBreakdown
						v-if="isDelegated(msg) && isExpanded(msg)"
						:breakdown="msg.model_breakdown"
					/>
				</div>
				<div class="msg-credits">
					<span v-if="msg.credits_used > 0" class="credit-amount">{{
						formatCredits(msg.credits_used)
					}}</span>
					<span v-else class="credit-zero">&mdash;</span>
					<span class="credit-label" v-if="msg.credits_used > 0">credits</span>
				</div>
			</div>
		</div>

		<p v-else class="empty-text">No messages in this conversation</p>
	</div>
</template>

<script setup>
import { computed, ref } from "vue";
import MessageModelBreakdown from "./MessageModelBreakdown.vue";

const props = defineProps({
	conversation: { type: Object, default: null },
	messages: { type: Array, default: () => [] },
	loading: { type: Boolean, default: false },
});

defineEmits(["back"]);

// Whether to inline-render the hidden context rows.
const showContext = ref(false);

// Message ids whose per-model delegation breakdown is expanded.
const expandedBreakdowns = ref(new Set());

function isDelegated(msg) {
	return Array.isArray(msg.model_breakdown) && msg.model_breakdown.length > 1;
}

function isExpanded(msg) {
	return expandedBreakdowns.value.has(msg.message_id);
}

function toggleBreakdown(msg) {
	const next = new Set(expandedBreakdowns.value);
	next.has(msg.message_id) ? next.delete(msg.message_id) : next.add(msg.message_id);
	expandedBreakdowns.value = next;
}

// A message is "context injection" if it's a user-role message whose
// content preview starts with one of the known context-injection markers
// the AR pipeline uses. We don't want to silently drop it (sometimes you
// need to see what was injected for debugging), just declutter by default.
const CONTEXT_MARKERS = [
	"# User Context (from previous conversations)",
	"# Team Instructions",
	"# Knowledge Base Context",
];

function isContextMessage(msg) {
	if (msg.role !== "user") return false;
	const preview = msg.content_preview || "";
	return CONTEXT_MARKERS.some((m) => preview.trimStart().startsWith(m));
}

// Annotate once so the template can render with `_isContext` without
// re-computing on every row.
const annotatedMessages = computed(() =>
	props.messages.map((m) => ({ ...m, _isContext: isContextMessage(m) }))
);

const visibleMessages = computed(() => annotatedMessages.value.filter((m) => !m._isContext));
const hiddenContextMessages = computed(() => annotatedMessages.value.filter((m) => m._isContext));
const hiddenContextCount = computed(() => hiddenContextMessages.value.length);

// When showContext is on, merge them back in and preserve original order
// by sorting on the index in annotatedMessages.
const displayedMessages = computed(() => {
	if (!showContext.value) return visibleMessages.value;
	return annotatedMessages.value;
});

function formatCredits(val) {
	if (!val) return "0";
	if (val < 1) return val.toFixed(2);
	return Math.round(val).toLocaleString();
}

function shortenModel(modelId) {
	if (!modelId) return "";
	// Remove date suffixes like -20250301
	return modelId.replace(/-\d{8}$/, "");
}

function formatDate(isoStr) {
	if (!isoStr) return "";
	return new Date(isoStr).toLocaleDateString([], {
		month: "short",
		day: "numeric",
		year: "numeric",
	});
}

function formatTime(isoStr) {
	if (!isoStr) return "";
	return new Date(isoStr).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
</script>

<style scoped>
.drilldown {
	display: flex;
	flex-direction: column;
	gap: 1rem;
}

.drilldown-header {
	display: flex;
	align-items: flex-start;
	gap: 1rem;
}

.back-btn {
	display: flex;
	align-items: center;
	gap: 0.25rem;
	padding: 0.375rem 0.75rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text-secondary);
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	cursor: pointer;
	flex-shrink: 0;
	transition: all 0.15s ease;
}

.back-btn:hover {
	color: var(--ql-text);
	background: var(--ql-subtle);
}

.back-icon {
	width: 16px;
	height: 16px;
}

.drilldown-meta {
	flex: 1;
	min-width: 0;
}

.drilldown-title {
	font-size: 1rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.drilldown-stats {
	display: flex;
	align-items: center;
	gap: 0.375rem;
	margin-top: 0.25rem;
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
}

.stat-sep {
	color: var(--ql-border);
}

.drilldown-loading {
	display: flex;
	justify-content: center;
	padding: 3rem;
}

.loading-spinner {
	width: 28px;
	height: 28px;
	border: 3px solid var(--ql-border);
	border-top-color: var(--ql-accent);
	border-radius: 50%;
	animation: spin 0.8s linear infinite;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

/* Message Timeline */
.message-timeline {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	overflow: hidden;
}

.context-summary {
	border-bottom: 1px solid var(--ql-border);
	background: var(--ql-bg);
}

.context-toggle {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	width: 100%;
	padding: 0.5rem 1rem;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	background: transparent;
	border: none;
	cursor: pointer;
	text-align: left;
	transition: background 0.15s ease;
}

.context-toggle:hover {
	background: var(--ql-subtle);
	color: var(--ql-text-secondary);
}

.context-chevron {
	width: 14px;
	height: 14px;
	transition: transform 0.2s ease;
}

.context-chevron.rotated {
	transform: rotate(90deg);
}

.context-hint {
	margin-left: auto;
	font-weight: 500;
	color: var(--ql-accent);
}

.is-context {
	background: var(--ql-bg);
}

.is-context .msg-preview {
	color: var(--ql-text-muted);
	font-size: 0.75rem;
}

.message-row {
	display: flex;
	align-items: flex-start;
	gap: 0.75rem;
	padding: 0.875rem 1rem;
	border-bottom: 1px solid var(--ql-border);
	transition: background 0.15s ease;
}

.message-row:last-child {
	border-bottom: none;
}

.message-row:hover {
	background: var(--ql-subtle);
}

.msg-role {
	flex-shrink: 0;
	padding-top: 0.125rem;
}

.role-badge {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 32px;
	height: 24px;
	font-size: 0.6875rem;
	font-weight: 700;
	border-radius: 0.375rem;
	text-transform: uppercase;
}

.role-badge.assistant {
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
}

.role-badge.user {
	background: var(--ql-subtle);
	color: var(--ql-text-secondary);
}

.role-badge.system {
	background: var(--ql-gold-soft);
	color: var(--ql-warning);
}

.msg-content {
	flex: 1;
	min-width: 0;
}

.msg-preview {
	font-size: 0.8125rem;
	color: var(--ql-text);
	line-height: 1.5;
	margin: 0;
	display: -webkit-box;
	-webkit-line-clamp: 2;
	-webkit-box-orient: vertical;
	overflow: hidden;
}

.is-user .msg-preview {
	color: var(--ql-text-secondary);
}

.msg-meta {
	display: flex;
	gap: 0.5rem;
	margin-top: 0.25rem;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.msg-model {
	background: var(--ql-bg);
	padding: 0.125rem 0.375rem;
	border-radius: 0.25rem;
	font-family: monospace;
	font-size: 0.6875rem;
}

.msg-badge {
	padding: 0.125rem 0.375rem;
	border-radius: 0.25rem;
	font-size: 0.6875rem;
	font-weight: 500;
}

.tool-badge {
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
}

.thinking-badge {
	background: var(--ql-gold-soft);
	color: var(--ql-warning);
}

/* Delegation badge + per-model breakdown */
.delegated-badge {
	display: inline-flex;
	align-items: center;
	gap: 0.2rem;
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
	border: none;
	cursor: pointer;
	font: inherit;
	font-size: 0.6875rem;
	font-weight: 600;
	padding: 0.125rem 0.375rem;
	border-radius: 0.25rem;
	transition: filter 0.15s ease;
}

.delegated-badge:hover {
	filter: brightness(0.95);
}

.delegated-chevron {
	width: 11px;
	height: 11px;
	transition: transform 0.2s ease;
}

.delegated-chevron.rotated {
	transform: rotate(90deg);
}

.msg-credits {
	flex-shrink: 0;
	text-align: right;
	min-width: 4rem;
	padding-top: 0.125rem;
}

.credit-amount {
	font-size: 0.875rem;
	font-weight: 700;
	color: var(--ql-text);
}

.credit-zero {
	font-size: 0.875rem;
	color: var(--ql-text-muted);
}

.credit-label {
	display: block;
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
}

.empty-text {
	font-size: 0.875rem;
	color: var(--ql-text-muted);
	text-align: center;
	padding: 2rem;
}

@media (max-width: 768px) {
	.message-row {
		padding: 0.625rem 0.75rem;
	}

	.msg-credits {
		min-width: 3rem;
	}

	.credit-label {
		display: none;
	}
}
</style>
