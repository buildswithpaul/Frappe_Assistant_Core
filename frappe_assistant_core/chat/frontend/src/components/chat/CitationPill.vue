<template>
	<span class="citation-pill-wrap" @mouseenter="openPopover" @mouseleave="closePopover">
		<button
			ref="pillRef"
			type="button"
			class="citation-pill"
			:title="source.document_name ? `Source: ${source.document_name}` : undefined"
			@click="onClick"
			@focus="openPopover"
			@blur="closePopover"
		>
			[{{ source.n }}]
		</button>

		<!-- Popover renders inside the same span — positioned relative to the pill.
         Hover delay is handled via CSS transition-delay so we don't flicker. -->
		<span
			v-if="hovered"
			ref="popoverRef"
			class="citation-popover"
			:style="{ '--pop-shift': `${shift}px` }"
			role="tooltip"
			@mouseenter="openPopover"
			@mouseleave="closePopover"
		>
			<span class="pop-doc-name">
				<svg viewBox="0 0 20 20" fill="currentColor" class="pop-icon" aria-hidden="true">
					<path
						d="M4 4a2 2 0 012-2h5.586A2 2 0 0113 2.586L16.414 6A2 2 0 0117 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z"
					/>
				</svg>
				{{ source.document_name || "Unknown document" }}
			</span>
			<span v-if="previewText" class="pop-preview"> "{{ previewText }}" </span>
			<span v-else class="pop-preview pop-preview-empty">
				(No passage preview available for this source.)
			</span>
			<button type="button" class="pop-open" @click.stop="onOpen">Open document →</button>
		</span>
	</span>
</template>

<script setup>
import { ref, computed, nextTick } from "vue";

// Gap kept between the popover and the edge of the area the reader can see.
const EDGE_GAP = 8;

const props = defineProps({
	source: {
		type: Object,
		required: true,
	},
});

const emit = defineEmits(["navigate", "preview-document"]);

const hovered = ref(false);
const pillRef = ref(null);
const popoverRef = ref(null);
const shift = ref(0);
let closeTimer = null;

// The nearest scrolling ancestor is the area the reader can see: the messages column in the SPA,
// the panel in the Desk widget. Anything past its edges sits under the sidebar or is cut off.
function visibleBounds(el) {
	for (let node = el.parentElement; node; node = node.parentElement) {
		const { overflowX, overflowY } = getComputedStyle(node);
		if (/auto|scroll|hidden|clip/.test(`${overflowX} ${overflowY}`)) return node.getBoundingClientRect();
	}
	return { left: 0, right: window.innerWidth };
}

async function keepInView() {
	shift.value = 0;
	await nextTick();
	const pop = popoverRef.value;
	if (!pop) return;
	const rect = pop.getBoundingClientRect();
	const bounds = visibleBounds(pop);
	const minLeft = bounds.left + EDGE_GAP;
	const maxRight = bounds.right - EDGE_GAP;
	if (rect.left < minLeft) shift.value = minLeft - rect.left;
	else if (rect.right > maxRight) shift.value = Math.max(maxRight - rect.right, minLeft - rect.left);
}

function openPopover() {
	if (closeTimer) {
		clearTimeout(closeTimer);
		closeTimer = null;
	}
	if (hovered.value) return;
	hovered.value = true;
	keepInView();
}

function closePopover() {
	// Small delay so users can drift from pill → popover without losing focus
	closeTimer = setTimeout(() => {
		hovered.value = false;
		closeTimer = null;
	}, 120);
}

function onClick() {
	emit("navigate", props.source.n);
}

function onOpen() {
	emit("preview-document", props.source);
	hovered.value = false;
}

const previewText = computed(() => {
	const raw = props.source.passage_preview;
	if (!raw || typeof raw !== "string") return "";
	const trimmed = raw.trim();
	// Add ellipsis if the retrieval layer trimmed at the 240-char cap
	if (trimmed.length >= 240) return trimmed + "…";
	return trimmed;
});
</script>

<style scoped>
.citation-pill-wrap {
	position: relative;
	display: inline-block;
	/* Prevent the pill from breaking awkwardly at line ends */
	white-space: nowrap;
}

.citation-pill {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	min-width: 1.25rem;
	height: 1.25rem;
	padding: 0 0.3125rem;
	margin: 0 0.0625rem;
	background-color: var(--ql-subtle);
	border: 1px solid var(--ql-border);
	border-radius: 0.3125rem;
	color: var(--ql-accent);
	font-size: 0.75rem;
	font-weight: 600;
	font-variant-numeric: tabular-nums;
	line-height: 1;
	cursor: pointer;
	transition: background-color 120ms ease, border-color 120ms ease, transform 120ms ease;
	vertical-align: baseline;
}

.citation-pill:hover,
.citation-pill:focus-visible {
	background-color: var(--ql-accent);
	border-color: var(--ql-accent);
	color: #ffffff;
	outline: none;
	transform: translateY(-1px);
}

.citation-popover {
	position: absolute;
	bottom: calc(100% + 0.5rem);
	left: 50%;
	transform: translateX(calc(-50% + var(--pop-shift, 0px)));
	z-index: 40;
	width: 22rem;
	max-width: calc(100vw - 2rem);
	padding: 0.75rem;
	background-color: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3), 0 6px 10px -6px rgba(0, 0, 0, 0.2);
	color: var(--ql-text);
	font-size: 0.8125rem;
	font-weight: 400;
	line-height: 1.5;
	white-space: normal;
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
	/* Trigger fade-in */
	animation: citation-pop-in 120ms ease-out;
}

/* Small arrow pointing down at the pill */
.citation-popover::after {
	content: "";
	position: absolute;
	top: 100%;
	/* Undo the popover's shift so the arrow still points at the pill */
	left: calc(50% - var(--pop-shift, 0px));
	transform: translateX(-50%);
	border: 6px solid transparent;
	border-top-color: var(--ql-surface);
	/* Subtle shadow seam */
	filter: drop-shadow(0 1px 0 var(--ql-border));
}

@keyframes citation-pop-in {
	from {
		opacity: 0;
		transform: translateX(calc(-50% + var(--pop-shift, 0px))) translateY(4px);
	}
	to {
		opacity: 1;
		transform: translateX(calc(-50% + var(--pop-shift, 0px))) translateY(0);
	}
}

.pop-doc-name {
	display: inline-flex;
	align-items: center;
	gap: 0.375rem;
	color: var(--ql-text);
	font-weight: 600;
	font-size: 0.8125rem;
}

.pop-icon {
	width: 0.875rem;
	height: 0.875rem;
	color: var(--ql-text-muted);
	flex-shrink: 0;
}

.pop-preview {
	color: var(--ql-text-muted);
	font-style: italic;
	font-size: 0.8125rem;
	line-height: 1.5;
	/* Clamp visible lines to keep the popover compact */
	display: -webkit-box;
	-webkit-line-clamp: 5;
	-webkit-box-orient: vertical;
	overflow: hidden;
}

.pop-preview-empty {
	font-style: normal;
	color: var(--ql-text-muted);
	opacity: 0.7;
}

.pop-open {
	align-self: flex-start;
	padding: 0.25rem 0.5rem;
	background: transparent;
	border: 1px solid var(--ql-accent);
	border-radius: 0.3125rem;
	color: var(--ql-accent);
	font-size: 0.75rem;
	font-weight: 500;
	cursor: pointer;
	transition: background-color 120ms ease, color 120ms ease;
}

.pop-open:hover {
	background-color: var(--ql-accent);
	color: #ffffff;
}
</style>
