<template>
	<Teleport to="body">
		<div class="artifact-modal" data-test="backdrop" @click.self="$emit('close')">
			<div class="modal-panel">
				<div class="modal-toolbar">
					<div class="zoom-controls">
						<button type="button" class="tool-btn" aria-label="Zoom out" @click="zoomOut">−</button>
						<span class="zoom-pct">{{ Math.round(scale * 100) }}%</span>
						<button type="button" class="tool-btn" aria-label="Zoom in" @click="zoomIn">+</button>
						<button type="button" class="tool-btn" @click="doFit">Fit</button>
						<button type="button" class="tool-btn" @click="reset">Reset</button>
					</div>
					<div class="right-controls">
						<button
							type="button"
							class="tool-btn primary"
							data-test="download-btn"
							@click="download"
						>
							⬇ PNG
						</button>
						<button type="button" class="tool-btn" aria-label="Close" @click="$emit('close')">
							✕
						</button>
					</div>
				</div>

				<div
					ref="viewportRef"
					class="modal-viewport"
					@wheel="onWheel"
					@pointerdown="onPointerDown"
				>
					<div
						ref="contentRef"
						class="viewport-content"
						data-test="viewport-content"
						:style="{ transform: transformStyle, transformOrigin: '0 0' }"
					/>
				</div>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from "vue";
import { useArtifactZoom } from "@/composables/useArtifactZoom";
import { logger } from "@/utils/logger";

const props = defineProps({
	capture: { type: Function, required: true },
	toPng: { type: Function, required: true },
	title: { type: String, default: "artifact" },
});

const emit = defineEmits(["close"]);

const viewportRef = ref(null);
const contentRef = ref(null);
let cleanupFn = () => {};

const { scale, transformStyle, onWheel, onPointerDown, zoomIn, zoomOut, reset, fit } =
	useArtifactZoom();

function doFit() {
	const node = contentRef.value?.firstElementChild;
	const vp = viewportRef.value;
	if (!node || !vp) return;
	const box = node.getBoundingClientRect();
	fit(
		{ width: box.width, height: box.height },
		{ width: vp.clientWidth, height: vp.clientHeight }
	);
}

async function download() {
	let dataUrl;
	try {
		dataUrl = await props.toPng();
	} catch (e) {
		// Export can realistically fail (canvas taint, fonts, OOM on huge charts).
		// Swallow into a logged error rather than an unhandled rejection; the
		// modal stays usable and the user can retry or close.
		logger.error("Artifact PNG export failed", e);
		return;
	}
	const a = document.createElement("a");
	a.href = dataUrl;
	a.download = `${props.title || "artifact"}.png`;
	document.body.appendChild(a);
	a.click();
	a.remove();
}

function onKeydown(e) {
	if (e.key === "Escape") emit("close");
}

onMounted(async () => {
	// Mount the captured node via appendChild (NO innerHTML — see spec security note).
	const captured = props.capture();
	if (captured?.node) {
		cleanupFn = captured.cleanup || (() => {});
		contentRef.value.appendChild(captured.node);
	}
	document.body.style.overflow = "hidden";
	document.addEventListener("keydown", onKeydown);
	await nextTick();
	doFit();
});

onBeforeUnmount(() => {
	document.removeEventListener("keydown", onKeydown);
	document.body.style.overflow = "";
	try {
		cleanupFn();
	} catch {
		/* cleanup best-effort */
	}
});
</script>

<style scoped>
.artifact-modal {
	position: fixed;
	inset: 0;
	z-index: 1100;
	display: flex;
	align-items: center;
	justify-content: center;
	background: rgba(0, 0, 0, 0.6);
	backdrop-filter: blur(4px);
}

.modal-panel {
	display: flex;
	flex-direction: column;
	width: 92vw;
	height: 88vh;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	overflow: hidden;
	box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.35);
}

.modal-toolbar {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 0.5rem 0.75rem;
	border-bottom: 1px solid var(--ql-border);
	background: var(--ql-surface);
}

.zoom-controls,
.right-controls {
	display: flex;
	align-items: center;
	gap: 0.375rem;
}

.zoom-pct {
	min-width: 3rem;
	text-align: center;
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
	font-variant-numeric: tabular-nums;
}

.tool-btn {
	min-width: 2rem;
	height: 2rem;
	padding: 0 0.625rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
	background: var(--ql-subtle);
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
	transition: background 0.15s ease;
}

.tool-btn:hover {
	background: var(--ql-border);
}

.tool-btn.primary {
	color: #fff;
	background: var(--ql-accent);
}

.tool-btn.primary:hover {
	background: var(--ql-accent-hover);
}

.modal-viewport {
	flex: 1;
	overflow: hidden;
	position: relative;
	cursor: grab;
	background: var(--ql-bg);
	touch-action: none;
}

.modal-viewport:active {
	cursor: grabbing;
}

.viewport-content {
	position: absolute;
	top: 0;
	left: 0;
	will-change: transform;
}
</style>
