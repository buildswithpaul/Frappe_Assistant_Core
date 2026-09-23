import { ref, computed } from "vue";

const MIN_SCALE = 0.1;
const MAX_SCALE = 10;
const STEP = 1.2; // zoom multiplier per button/notch
const FIT_PADDING = 0.9; // leave a 10% margin when fitting

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

/**
 * Pan/zoom state + math for an artifact viewport.
 *
 * Pure: holds scale + translate (tx, ty) and exposes handlers/actions. The
 * consuming component binds `transformStyle` to the inner node and wires
 * `onWheel` / `onPointerDown`. The transform model is:
 *   screen = translate(tx, ty) * scale(s) applied to content coordinates,
 * i.e. screenPoint = (tx + s*cx, ty + s*cy).
 */
export function useArtifactZoom() {
	const scale = ref(1);
	const tx = ref(0);
	const ty = ref(0);

	const transformStyle = computed(
		() => `translate(${tx.value}px, ${ty.value}px) scale(${scale.value})`
	);

	function pan(dx, dy) {
		tx.value += dx;
		ty.value += dy;
	}

	function reset() {
		scale.value = 1;
		tx.value = 0;
		ty.value = 0;
	}

	// Zoom about a fixed screen point (sx, sy) so that point stays put.
	function zoomAbout(sx, sy, factor) {
		const next = clamp(scale.value * factor, MIN_SCALE, MAX_SCALE);
		const applied = next / scale.value; // effective factor after clamping
		// Keep (sx, sy) fixed: t' = s_screen - applied*(s_screen - t)
		tx.value = sx - applied * (sx - tx.value);
		ty.value = sy - applied * (sy - ty.value);
		scale.value = next;
	}

	function zoomIn() {
		zoomAbout(tx.value, ty.value, STEP); // button zoom anchors the content origin (top-left), by design
	}

	function zoomOut() {
		zoomAbout(tx.value, ty.value, 1 / STEP);
	}

	function onWheel(e) {
		e.preventDefault();
		const rect = e.currentTarget.getBoundingClientRect();
		const sx = e.clientX - rect.left;
		const sy = e.clientY - rect.top;
		const factor = e.deltaY < 0 ? STEP : 1 / STEP;
		zoomAbout(sx, sy, factor);
	}

	function fit(content, viewport) {
		if (!content?.width || !content?.height || !viewport?.width || !viewport?.height) {
			reset();
			return;
		}
		const s = Math.min(
			(viewport.width / content.width) * FIT_PADDING,
			(viewport.height / content.height) * FIT_PADDING,
			1 // never upscale past natural size on fit
		);
		scale.value = s;
		tx.value = (viewport.width - content.width * s) / 2;
		ty.value = (viewport.height - content.height * s) / 2;
	}

	// Drag-to-pan via Pointer Events. Self-tears-down its move/up/cancel
	// listeners on pointerup or pointercancel, so the caller has nothing to
	// clean up on unmount.
	function onPointerDown(e) {
		const startX = e.clientX;
		const startY = e.clientY;
		const originX = tx.value;
		const originY = ty.value;
		const target = e.currentTarget;
		target.setPointerCapture?.(e.pointerId);

		function move(ev) {
			tx.value = originX + (ev.clientX - startX);
			ty.value = originY + (ev.clientY - startY);
		}
		function up(ev) {
			target.releasePointerCapture?.(ev.pointerId);
			target.removeEventListener("pointermove", move);
			target.removeEventListener("pointerup", up);
			target.removeEventListener("pointercancel", up);
		}
		target.addEventListener("pointermove", move);
		target.addEventListener("pointerup", up);
		target.addEventListener("pointercancel", up);
	}

	return {
		scale,
		tx,
		ty,
		transformStyle,
		pan,
		reset,
		zoomIn,
		zoomOut,
		onWheel,
		onPointerDown,
		fit,
	};
}
