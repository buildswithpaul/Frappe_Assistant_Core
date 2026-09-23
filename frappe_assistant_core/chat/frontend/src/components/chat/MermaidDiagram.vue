<template>
	<ExpandableArtifact
		:capture="captureSvg"
		:can-capture="hasSvg"
		:to-png="exportPng"
		:disabled="isStreaming"
		title="diagram"
	>
		<div class="mermaid-container">
			<div ref="container" class="mermaid-content"></div>
			<div v-if="error" class="mermaid-error">
				<svg class="error-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
					/>
				</svg>
				<span>Failed to render diagram</span>
			</div>
		</div>
	</ExpandableArtifact>
</template>

<script setup>
import { ref, onMounted, watch, nextTick } from "vue";
import mermaid from "mermaid";
import { logger } from "@/utils/logger";
import ExpandableArtifact from "./artifact/ExpandableArtifact.vue";
import { svgToPng } from "./artifact/svgToPng";

const props = defineProps({
	content: {
		type: String,
		required: true,
	},
	isStreaming: {
		type: Boolean,
		default: false,
	},
});

const container = ref(null);
const error = ref(false);
const hasRendered = ref(false);
let initialized = false;

// Initialize mermaid with configuration
function initMermaid() {
	if (initialized) return;

	mermaid.initialize({
		startOnLoad: false,
		theme: "neutral",
		securityLevel: "loose",
		fontFamily: "inherit",
		htmlLabels: false,
		flowchart: {
			useMaxWidth: true,
			htmlLabels: false,
			curve: "basis",
		},
		sequence: {
			useMaxWidth: true,
		},
		pie: {
			useMaxWidth: true,
		},
	});

	initialized = true;
}

async function renderDiagram() {
	if (!container.value || !props.content) return;

	error.value = false;

	try {
		initMermaid();

		// Generate unique ID for this diagram
		const id = `mermaid-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

		// Clean content: decode HTML entities and strip <br> tags that LLMs sometimes inject.
		// &amp; is decoded LAST. Decoding it first turns "&amp;lt;" into "&lt;",
		// which the next pass then turns into "<" — a literal "&lt;" the author
		// escaped on purpose comes out as markup.
		const cleaned = props.content
			.trim()
			.replace(/<br\s*\/?>/gi, "\n")
			.replace(/&gt;/g, ">")
			.replace(/&lt;/g, "<")
			.replace(/&quot;/g, '"')
			.replace(/&#039;/g, "'")
			.replace(/&amp;/g, "&");

		// Render the diagram
		const { svg } = await mermaid.render(id, cleaned);

		// Insert the rendered SVG
		container.value.innerHTML = svg;
		hasRendered.value = true;
	} catch (e) {
		logger.error("Mermaid rendering error:", e);
		error.value = true;
		hasRendered.value = false;
		// Show the raw content as fallback
		container.value.innerHTML = `<pre class="mermaid-fallback"><code>${escapeHtml(
			props.content
		)}</code></pre>`;
	}
}

function escapeHtml(text) {
	const map = {
		"&": "&amp;",
		"<": "&lt;",
		">": "&gt;",
		'"': "&quot;",
		"'": "&#039;",
	};
	return text.replace(/[&<>"']/g, (m) => map[m]);
}

// Cheap predicate for ExpandableArtifact visibility — does a rendered <svg>
// exist? Allocation-free (no clone), safe to call on every render. Returns
// false in the error/fallback state (no <svg> produced).
function hasSvg() {
	return hasRendered.value && !!container.value?.querySelector("svg");
}

// Capture adapter (modal-only): clone the rendered <svg> so the modal zooms an
// independent copy. Mermaid renders with useMaxWidth, leaving the SVG with an
// inline max-width style and width="100%" — in the modal that makes the clone
// lay out small and the browser rasterize it small, so CSS zoom upscales a tiny
// bitmap (blur). We strip those constraints and pin the clone to its intrinsic
// viewBox size, so it lays out full-size and stays crisp when zoomed.
function captureSvg() {
	const svg = container.value?.querySelector("svg");
	if (!svg) return null;
	const clone = svg.cloneNode(true);

	// Derive intrinsic size from the viewBox (true authored dimensions).
	const vb = (clone.getAttribute("viewBox") || "").trim().split(/[\s,]+/).map(Number);
	if (vb.length === 4 && vb[2] > 0 && vb[3] > 0) {
		clone.setAttribute("width", String(vb[2]));
		clone.setAttribute("height", String(vb[3]));
	} else {
		// No usable viewBox: fall back to the live element's rendered box so the
		// clone at least keeps a concrete pixel size rather than width="100%".
		const box = svg.getBoundingClientRect();
		if (box.width > 0 && box.height > 0) {
			clone.setAttribute("width", String(Math.round(box.width)));
			clone.setAttribute("height", String(Math.round(box.height)));
		}
	}

	// Remove the max-width / width:100% constraints mermaid injects via inline
	// style, so the explicit width/height above actually drive layout.
	clone.style.removeProperty("max-width");
	clone.style.removeProperty("width");
	clone.style.removeProperty("height");

	return { node: clone, cleanup: () => {} }; // static clone — nothing to dispose
}

// Export adapter: serialize the rendered <svg> to a 2x white-background PNG.
function exportPng() {
	const svg = container.value?.querySelector("svg");
	if (!svg) return Promise.reject(new Error("No diagram to export"));
	return svgToPng(svg, 2);
}

onMounted(() => {
	nextTick(renderDiagram);
});

watch(
	() => props.content,
	() => {
		nextTick(renderDiagram);
	}
);
</script>

<style scoped>
.mermaid-container {
	margin: 1rem 0;
	padding: 1rem;
	background-color: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	overflow-x: auto;
}

.mermaid-content {
	display: flex;
	justify-content: center;
}

.mermaid-content :deep(svg) {
	max-width: 100%;
	height: auto;
}

.mermaid-error {
	display: flex;
	align-items: center;
	justify-content: center;
	gap: 0.5rem;
	padding: 1rem;
	color: var(--ql-text-muted);
	font-size: 0.875rem;
}

.error-icon {
	width: 1.25rem;
	height: 1.25rem;
	color: #f59e0b;
}

.mermaid-content :deep(.mermaid-fallback) {
	margin: 0;
	padding: 0.75rem;
	background-color: var(--ql-bg);
	border-radius: 0.375rem;
	font-size: 0.8125rem;
	white-space: pre-wrap;
	word-break: break-word;
}

.mermaid-content :deep(.mermaid-fallback code) {
	background: transparent;
	padding: 0;
}
</style>
