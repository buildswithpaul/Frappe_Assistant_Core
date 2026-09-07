<template>
	<div class="message-blocks">
		<template v-for="segment in groupedContent" :key="segment.id">
			<!-- Processing Card: groups consecutive thinking + tool_call blocks -->
			<ProcessingCard
				v-if="segment.type === 'processing_group'"
				:blocks="segment.blocks"
				:is-streaming="isStreaming"
				:is-expanded="processingGroupExpanded[segment.id] ?? (isStreaming && !userCollapsed)"
				:message-index="messageIndex"
				@toggle="toggleProcessingGroup(segment.id)"
				@toggle-block="(msgIdx, blockId) => $emit('toggleBlock', msgIdx, blockId)"
			/>

			<!-- Interaction Card: HITL approval + LLM questions -->
			<InteractionCard
				v-else-if="segment.type === 'interaction'"
				:block="segment"
				@approve="(blockId, responses) => $emit('approve', blockId, responses)"
				@reject="(blockId, responses) => $emit('reject', blockId, responses)"
			/>

			<!-- Text Block - Parse for rich blocks (charts, mermaid, callouts, etc.) -->
			<div v-else-if="segment.type === 'text'" class="text-block">
				<template
					v-for="(part, idx) in parseTextBlock(cleanCitations(segment.content))"
					:key="`${segment.id}-${idx}`"
				>
					<!-- Rich block (chart, mermaid, callout) — render as-is -->
					<component
						v-if="part.type === 'component'"
						:is="part.component"
						v-bind="part.props"
						:is-streaming="isStreaming"
					/>
					<!-- Markdown HTML with citation markers — splice in CitationPill
               components between HTML fragments. Wrapping in one container
               keeps browser-auto-closing consistent when the [N] marker sits
               inside a paragraph or table cell. -->
					<div v-else-if="hasCitations(part.html)" class="text-with-citations">
						<template
							v-for="(sub, sIdx) in splitOnCitations(part.html)"
							:key="`${segment.id}-${idx}-${sIdx}`"
						>
							<CitationPill
								v-if="sub.type === 'pill'"
								:source="sub.source"
								@navigate="onCitationNavigate"
								@preview-document="(doc) => $emit('previewDocument', doc)"
							/>
							<span v-else class="text-citation-fragment" v-html="sub.html"></span>
						</template>
					</div>
					<!-- Plain markdown HTML (no citations) -->
					<div v-else v-html="part.html"></div>
				</template>
			</div>

			<!-- Sources Block: RAG citations footer -->
			<SourcesBlock
				v-else-if="segment.type === 'sources'"
				ref="sourcesBlockRef"
				:items="segment.items || []"
				@preview-document="(doc) => $emit('previewDocument', doc)"
			/>

			<!-- Generated Documents Block: PDFs (and other files) produced by
			     the generate_document tool during this turn. -->
			<GeneratedDocumentsBlock
				v-else-if="segment.type === 'generated_documents'"
				:items="segment.items || []"
				@preview-document="(doc) => $emit('previewDocument', doc)"
			/>

			<!-- Workflow Created Block: card + Open-in-builder button for
			     agent/workflow builder tool results. -->
			<WorkflowCreatedBlock
				v-else-if="segment.type === 'workflow_created'"
				:block="segment"
			/>
		</template>

		<!-- Streaming indicator when actively streaming text -->
		<div v-if="isStreaming && hasActiveTextBlock" class="streaming-indicator">
			<span class="streaming-dot"></span>
			<span class="streaming-dot"></span>
			<span class="streaming-dot"></span>
		</div>

		<!-- Processing indicator when waiting between blocks -->
		<ProcessingIndicator v-if="showProcessingIndicator" :blocks="blocks" />
	</div>
</template>

<script setup>
import { computed, reactive, ref, watch, onMounted } from "vue";
import ProcessingCard from "./ProcessingCard.vue";
import ProcessingIndicator from "./ProcessingIndicator.vue";
import InteractionCard from "./InteractionCard.vue";
import SourcesBlock from "./SourcesBlock.vue";
import GeneratedDocumentsBlock from "./GeneratedDocumentsBlock.vue";
import WorkflowCreatedBlock from "./WorkflowCreatedBlock.vue";
import CitationPill from "./CitationPill.vue";
import { parseRichBlocks } from "./richBlocks/parser";
import { renderMarkdown as renderMd, ensureHljs } from "@/utils/markdown.js";
import { shouldShowProcessingIndicator } from "./indicatorVisibility";

const props = defineProps({
	blocks: {
		type: Array,
		required: true,
	},
	messageIndex: {
		type: Number,
		required: true,
	},
	isStreaming: {
		type: Boolean,
		default: false,
	},
});

defineEmits(["toggleBlock", "approve", "reject", "previewDocument"]);

// Bump on hljs load so computed renders re-run with syntax highlighting
// once the chunk arrives. First paint uses plain escaped code (instant);
// the upgrade happens after a microtask without blocking initial render.
const hljsReady = ref(0);
onMounted(() => {
	ensureHljs().then(() => {
		hljsReady.value++;
	});
});

// Track expand/collapse state per processing group
const processingGroupExpanded = reactive({});

// Each narration line closes a group, so a long turn mints several cards. The
// cards still to come have no entry of their own, so they fall back to whichever
// way the user last toggled one — collapse means "stop showing me the work",
// re-expanding says the opposite. Only a toggle made mid-turn counts: opening a
// card to read finished history isn't a preference about work still to come.
const userCollapsed = ref(false);

function toggleProcessingGroup(groupId) {
	// Read the effective state, not the raw entry — an auto-expanded card has no
	// entry yet, and `!undefined` would make the first click a no-op.
	const wasExpanded =
		processingGroupExpanded[groupId] ?? (props.isStreaming && !userCollapsed.value);
	processingGroupExpanded[groupId] = !wasExpanded;
	if (props.isStreaming) userCollapsed.value = wasExpanded;
}

// Auto-collapse processing groups when streaming ends
watch(
	() => props.isStreaming,
	(streaming, wasStreaming) => {
		if (wasStreaming && !streaming) {
			for (const key of Object.keys(processingGroupExpanded)) {
				processingGroupExpanded[key] = false;
			}
			userCollapsed.value = false;
		}
	}
);

// A processing_group holds only thinking, tool_call and resolved interaction
// blocks — the events the stream actually typed as work. Any text block closes
// the group and renders at top level, so the model's prose is never buried in
// a card that collapses when the turn ends.
const groupedContent = computed(() => {
	if (!props.blocks?.length) return [];

	const segments = [];
	let currentGroup = null;
	// Set once a group has taken an approval receipt: siblings of that approval
	// still belong to it, but the next unit of work starts a new card.
	let sealedByApproval = false;

	for (const block of props.blocks) {
		if (block.type === "interaction") {
			if (block.status === "pending") {
				// Pending interactions render at top level — prominent and actionable
				currentGroup = null;
				sealedByApproval = false;
				segments.push(block);
			} else {
				// Resolved interactions join the card that already holds this
				// turn's work — it shows the tool name + inputs when expanded, so
				// a standalone card would duplicate that. Never mint a group here:
				// an interaction carries the SAME id as the tool_call it gated, so
				// `pg_<tool_id>` would collide with that tool's own group and one
				// chevron would drive two cards.
				if (currentGroup) {
					currentGroup.blocks.push(block);
					// Seal rather than close: AR gates parallel tool calls in one
					// batch, so the sibling approvals that follow are receipts for
					// this same card, not the start of the next step.
					sealedByApproval = true;
				} else {
					segments.push(block);
				}
			}
		} else if (block.type === "thinking" || block.type === "tool_call") {
			if (!currentGroup || sealedByApproval) {
				currentGroup = {
					type: "processing_group",
					id: `pg_${block.id}`,
					blocks: [],
				};
				segments.push(currentGroup);
				sealedByApproval = false;
			}
			currentGroup.blocks.push(block);
		} else if (
			block.type === "sources" ||
			block.type === "generated_documents" ||
			block.type === "workflow_created"
		) {
			// Footer blocks (RAG sources, generated documents) always render at
			// their natural position (after the last text block) as standalone
			// segments — never inside a processing group.
			currentGroup = null;
			sealedByApproval = false;
			segments.push(block);
		} else if (block.type === "text") {
			// A whitespace-only chunk would otherwise split one card in two
			// behind an invisible div — appendStreamChunk has no emptiness guard.
			if (!block.content || !block.content.trim()) continue;
			currentGroup = null;
			sealedByApproval = false;
			segments.push(block);
		}
	}

	return segments;
});

// Check if there's an active text block being streamed
const hasActiveTextBlock = computed(() => {
	if (!props.blocks || props.blocks.length === 0) return false;
	const lastBlock = props.blocks[props.blocks.length - 1];
	return lastBlock && lastBlock.type === "text";
});

// Check if we should show the processing indicator
const showProcessingIndicator = computed(() =>
	shouldShowProcessingIndicator(props.isStreaming, props.blocks)
);

// Render markdown content. Reading hljsReady creates a reactive dep so
// computed renderers re-run once highlight.js finishes loading.
function renderMarkdown(content) {
	if (!content) return "";
	// eslint-disable-next-line no-unused-expressions
	hljsReady.value;
	return renderMd(content);
}

// Parse text block content for rich blocks (charts, mermaid, callouts, etc.)
function parseTextBlock(content) {
	return parseRichBlocks(content, renderMarkdown);
}

// Highest valid citation index in this message, derived from the sources block.
// -1 when there are no sources attached — in that case every [N] is invalid.
const maxCitation = computed(() => {
	const sourcesBlock = props.blocks?.find((b) => b.type === "sources");
	if (!sourcesBlock) return -1;
	const items = sourcesBlock.items || [];
	return items.length;
});

// Strip [N] markers that can't resolve to a known source. The model sometimes
// invents citations like [7] when only 3 sources were retrieved, or emits [N]
// when no sources exist at all. Rendering those as literal text misleads the
// user into clicking nothing. We filter at render time only — the raw model
// output stays in message.blocks[].content as the source of truth.
function cleanCitations(content) {
	if (!content) return content;
	const max = maxCitation.value;
	return content.replace(/\[(\d+)\]/g, (match, n) => {
		const num = parseInt(n, 10);
		return num >= 1 && num <= max ? match : "";
	});
}

// Map n → source entry, so CitationPill can render the document name + passage
// preview in its hover popover. Derived from the sources block on this message.
const sourcesMap = computed(() => {
	const sourcesBlock = props.blocks?.find((b) => b.type === "sources");
	const items = sourcesBlock?.items || [];
	const map = new Map();
	for (const item of items) {
		if (typeof item.n === "number") map.set(item.n, item);
	}
	return map;
});

// [N] markers are expected to sit inside text nodes after marked.parse —
// never inside tag names or attribute values. That lets us regex-split the
// post-markdown HTML directly.
const CITATION_REGEX = /\[(\d+)\]/g;

function hasCitations(html) {
	if (!html || html.indexOf("[") === -1) return false;
	if (sourcesMap.value.size === 0) return false;
	// Cheap probe first, then verify at least one n is resolvable
	CITATION_REGEX.lastIndex = 0;
	let match;
	while ((match = CITATION_REGEX.exec(html)) !== null) {
		const n = parseInt(match[1], 10);
		if (sourcesMap.value.has(n)) return true;
	}
	return false;
}

// Walk the HTML string, emitting alternating html fragments and pill tokens.
// Both fragments and pills render inside the same parent `text-with-citations`
// container, so broken markdown tags (splitting across a [N] mid-paragraph)
// still get re-stitched by the browser's HTML parser.
function splitOnCitations(html) {
	const map = sourcesMap.value;
	const out = [];
	if (!html) return out;
	if (map.size === 0) {
		out.push({ type: "html", html });
		return out;
	}

	let lastIndex = 0;
	let match;
	CITATION_REGEX.lastIndex = 0;
	while ((match = CITATION_REGEX.exec(html)) !== null) {
		const n = parseInt(match[1], 10);
		const source = map.get(n);
		if (!source) continue;
		if (match.index > lastIndex) {
			out.push({ type: "html", html: html.slice(lastIndex, match.index) });
		}
		out.push({ type: "pill", source });
		lastIndex = match.index + match[0].length;
	}
	if (lastIndex < html.length) {
		out.push({ type: "html", html: html.slice(lastIndex) });
	}
	return out;
}

// CitationPill emits 'navigate' with the citation n. Forward to the matching
// SourcesBlock instance so it can expand itself + scroll + flash the item.
const sourcesBlockRef = ref(null);

function onCitationNavigate(n) {
	const block = sourcesBlockRef.value;
	if (block && typeof block.flashItem === "function") {
		block.flashItem(n);
	}
}
</script>

<style scoped>
.message-blocks {
	display: flex;
	flex-direction: column;
}

/* Text block inherits message-text styles from parent */
.text-block {
	font-size: 0.9375rem;
	line-height: 1.6;
	color: var(--ql-text);
}

/* Container that wraps HTML fragments and inline CitationPills together.
   The fragment spans carry partial block-level HTML (<p> open without </p>,
   etc.) — the browser parser auto-closes them as if they lived in one div,
   so visual flow stays identical to a plain <div v-html="...">. */
.text-with-citations {
	display: block;
}

.text-citation-fragment {
	display: contents;
}

/* Markdown styles */
/* Quiet Ledger: serif display headings + tabular-mono table figures.
   Applied here (not .faco-prose) because assistant markdown renders via
   v-html inside .text-block — :deep() pierces scoped style into that HTML. */
.text-block :deep(h1),
.text-block :deep(h2),
.text-block :deep(h3) {
	font-family: var(--ql-font-display);
	color: var(--ql-text);
	font-weight: 600;
	letter-spacing: -0.01em;
}

.text-block :deep(td),
.text-block :deep(th) {
	font-variant-numeric: tabular-nums;
}

.text-block :deep(td) {
	font-family: var(--ql-font-mono);
}

.text-block :deep(p) {
	margin-bottom: 0.75rem;
}

.text-block :deep(p:last-child) {
	margin-bottom: 0;
}

.text-block :deep(ul),
.text-block :deep(ol) {
	margin-bottom: 0.75rem;
	padding-left: 1.5rem;
}

.text-block :deep(ul) {
	list-style: disc;
}

.text-block :deep(ol) {
	list-style: decimal;
}

.text-block :deep(li) {
	margin-bottom: 0.25rem;
}

.text-block :deep(code) {
	padding: 0.125rem 0.375rem;
	background-color: var(--ql-subtle);
	border-radius: 0.25rem;
	font-size: 0.875em;
	font-family: "SF Mono", "Monaco", "Cascadia Code", monospace;
}

.text-block :deep(pre) {
	margin: 0.75rem 0;
	padding: 1rem;
	background-color: #1e293b;
	border-radius: 0.5rem;
	overflow-x: auto;
}

.text-block :deep(pre code) {
	padding: 0;
	background: transparent;
	color: #e2e8f0;
	font-size: 0.875rem;
}

.text-block :deep(strong) {
	font-weight: 600;
}

.text-block :deep(a) {
	color: var(--ql-accent);
	text-decoration: underline;
}

.text-block :deep(blockquote) {
	margin: 0.75rem 0;
	padding-left: 1rem;
	border-left: 3px solid var(--ql-accent);
	color: var(--ql-text-muted);
}

.text-block :deep(table) {
	width: 100%;
	margin: 0.75rem 0;
	border-collapse: collapse;
	display: block;
	overflow-x: auto;
}

.text-block :deep(th),
.text-block :deep(td) {
	padding: 0.5rem 0.75rem;
	border: 1px solid var(--ql-border);
	text-align: left;
}

.text-block :deep(th) {
	background-color: var(--ql-subtle);
	font-weight: 600;
}

/* Streaming indicator */
.streaming-indicator {
	display: flex;
	gap: 0.25rem;
	margin-top: 0.5rem;
}

.streaming-dot {
	width: 0.375rem;
	height: 0.375rem;
	background-color: var(--ql-accent);
	border-radius: 50%;
	animation: streaming-pulse 1.4s infinite;
}

.streaming-dot:nth-child(1) {
	animation-delay: 0s;
}
.streaming-dot:nth-child(2) {
	animation-delay: 0.2s;
}
.streaming-dot:nth-child(3) {
	animation-delay: 0.4s;
}

@keyframes streaming-pulse {
	0%,
	60%,
	100% {
		opacity: 0.3;
		transform: scale(0.8);
	}
	30% {
		opacity: 1;
		transform: scale(1);
	}
}
</style>
