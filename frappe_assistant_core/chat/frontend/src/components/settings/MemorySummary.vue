<template>
	<div class="memory-summary">
		<!-- Loading State -->
		<div v-if="loading" class="summary-loading">
			<div class="skeleton-block"></div>
			<div class="skeleton-block short"></div>
			<div class="skeleton-block"></div>
			<div class="skeleton-block medium"></div>
			<p class="generating-text">Generating your profile summary...</p>
		</div>

		<!-- Error State -->
		<div v-else-if="error" class="summary-error">
			<p>{{ error }}</p>
			<button class="retry-btn" @click="$emit('regenerate')">Try Again</button>
		</div>

		<!-- No Summary (insufficient memories) -->
		<div v-else-if="!summary" class="summary-empty">
			<svg
				class="empty-icon"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				width="32"
				height="32"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="1.5"
					d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
				/>
			</svg>
			<p class="empty-title">Not enough memories yet</p>
			<p class="empty-description">
				Keep chatting and I'll build a summary of what I've learned about you. At least a
				few conversations are needed.
			</p>
		</div>

		<!-- Summary Content -->
		<div v-else class="summary-content">
			<!-- Shown rather than blocking on the refresh: the text below is the
			     last good summary, which beats a skeleton every time. -->
			<div v-if="stale" class="summary-updating">
				<span class="updating-dot"></span>
				Updating with your latest memories&hellip;
			</div>
			<div class="summary-body" v-html="renderedSummary"></div>
			<div class="summary-footer">
				<span class="footer-note"
					>This summary is generated from your memories. Switch to
					<strong>Memories</strong> view to manage individual items.</span
				>
				<button class="regenerate-btn" @click="$emit('regenerate')" :disabled="loading">
					<svg
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						width="14"
						height="14"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
						/>
					</svg>
					Regenerate
				</button>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import DOMPurify from "dompurify";

const props = defineProps({
	summary: { type: String, default: null },
	loading: { type: Boolean, default: false },
	error: { type: String, default: null },
	// The server is regenerating behind the text being shown. Not a loading
	// state — there is content on screen — so it reads as a quiet note.
	stale: { type: Boolean, default: false },
});

defineEmits(["regenerate"]);

/**
 * Simple markdown renderer for the summary.
 * Handles: ## headings, **bold**, paragraphs, bullet lists
 */
const renderedSummary = computed(() => {
	if (!props.summary) return "";

	let html = props.summary
		// Escape HTML
		.replace(/&/g, "&amp;")
		.replace(/</g, "&lt;")
		.replace(/>/g, "&gt;")
		// ## Headings
		.replace(/^## (.+)$/gm, '<h3 class="summary-heading">$1</h3>')
		// **bold**
		.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
		// Bullet lists (- item)
		.replace(/^- (.+)$/gm, "<li>$1</li>")
		// Wrap consecutive <li> in <ul>
		.replace(/((?:<li>.*<\/li>\n?)+)/g, "<ul>$1</ul>")
		// Paragraphs (double newline)
		.replace(/\n\n/g, "</p><p>")
		// Single newlines within paragraphs
		.replace(/\n/g, "<br>");

	// Wrap in paragraph tags if not starting with a heading
	if (!html.startsWith("<h3")) {
		html = "<p>" + html + "</p>";
	}

	// Clean up empty paragraphs
	html = html.replace(/<p>\s*<\/p>/g, "");
	// Fix paragraphs around headings
	html = html.replace(/<p><h3/g, "<h3");
	html = html.replace(/<\/h3><\/p>/g, "</h3>");
	html = html.replace(/<\/h3><br>/g, "</h3>");
	// Ensure content after headings is wrapped in <p>
	html = html.replace(/<\/h3>(?!<h3|<p|<ul|$)/g, "</h3><p>");

	// Belt-and-suspenders: entities are already escaped above, but route the
	// final HTML through DOMPurify so any future edit that adds unescaped
	// interpolation can't introduce XSS.
	return DOMPurify.sanitize(html);
});
</script>

<style scoped>
.memory-summary {
	margin-top: 0.5rem;
}

/* Loading skeleton */
.summary-loading {
	padding: 1rem 0;
}

.skeleton-block {
	height: 14px;
	background: var(--ql-border, #e2e8f0);
	border-radius: 4px;
	margin-bottom: 0.75rem;
	animation: skeleton-pulse 1.5s ease-in-out infinite;
	width: 100%;
}

.skeleton-block.short {
	width: 60%;
}
.skeleton-block.medium {
	width: 80%;
}

@keyframes skeleton-pulse {
	0%,
	100% {
		opacity: 0.4;
	}
	50% {
		opacity: 0.8;
	}
}

.generating-text {
	font-size: 0.8rem;
	color: var(--ql-text-muted, #64748b);
	text-align: center;
	margin-top: 1rem;
}

/* Error */
.summary-error {
	text-align: center;
	padding: 1.5rem;
	color: var(--ql-text-muted, #64748b);
}

.retry-btn {
	margin-top: 0.5rem;
	padding: 0.25rem 0.75rem;
	font-size: 0.8rem;
	border: 1px solid var(--ql-border, #e2e8f0);
	border-radius: 6px;
	background: transparent;
	cursor: pointer;
	color: var(--ql-text, #1e293b);
}

.retry-btn:hover {
	background: var(--ql-subtle, #f1f5f9);
}

/* Empty state */
.summary-empty {
	text-align: center;
	padding: 2rem 1rem;
}

.empty-icon {
	color: var(--ql-text-muted, #94a3b8);
	margin-bottom: 0.75rem;
}

.empty-title {
	font-weight: 600;
	font-size: 0.95rem;
	color: var(--ql-text, #1e293b);
	margin-bottom: 0.25rem;
}

.empty-description {
	font-size: 0.85rem;
	color: var(--ql-text-muted, #64748b);
	max-width: 320px;
	margin: 0 auto;
	line-height: 1.5;
}

/* Summary content */
.summary-updating {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	margin-bottom: 0.75rem;
}

.updating-dot {
	width: 0.4rem;
	height: 0.4rem;
	border-radius: 50%;
	background: var(--ql-accent);
	animation: updating-pulse 1.4s ease-in-out infinite;
}

@keyframes updating-pulse {
	0%,
	100% {
		opacity: 0.3;
	}
	50% {
		opacity: 1;
	}
}

@media (prefers-reduced-motion: reduce) {
	.updating-dot {
		animation: none;
		opacity: 0.7;
	}
}

.summary-content {
	padding: 0.25rem 0;
}

.summary-body {
	font-size: 0.875rem;
	line-height: 1.7;
	color: var(--ql-text, #1e293b);
}

.summary-body :deep(h3.summary-heading) {
	font-size: 0.75rem;
	font-weight: 600;
	text-transform: uppercase;
	letter-spacing: 0.04em;
	color: var(--ql-text-muted, #64748b);
	margin: 1.25rem 0 0.4rem 0;
	padding-bottom: 0.25rem;
	border-bottom: 1px solid var(--ql-border, #e2e8f0);
}

.summary-body :deep(h3.summary-heading:first-child) {
	margin-top: 0;
}

.summary-body :deep(p) {
	margin: 0.4rem 0;
}

.summary-body :deep(strong) {
	font-weight: 600;
	color: var(--ql-text, #1e293b);
}

.summary-body :deep(ul) {
	padding-left: 1.25rem;
	margin: 0.4rem 0;
}

.summary-body :deep(li) {
	margin-bottom: 0.2rem;
}

/* Footer */
.summary-footer {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 1rem;
	margin-top: 1.5rem;
	padding-top: 0.75rem;
	border-top: 1px solid var(--ql-border, #e2e8f0);
}

.footer-note {
	font-size: 0.75rem;
	color: var(--ql-text-muted, #94a3b8);
	line-height: 1.4;
}

.footer-note strong {
	font-weight: 600;
}

.regenerate-btn {
	display: inline-flex;
	align-items: center;
	gap: 0.35rem;
	padding: 0.3rem 0.65rem;
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-accent);
	border: 1px solid var(--ql-accent);
	border-radius: 6px;
	background: transparent;
	cursor: pointer;
	white-space: nowrap;
	transition: all 0.15s ease;
}

.regenerate-btn:hover:not(:disabled) {
	background: var(--ql-accent);
	color: white;
}

.regenerate-btn:disabled {
	opacity: 0.5;
	cursor: not-allowed;
}
</style>
