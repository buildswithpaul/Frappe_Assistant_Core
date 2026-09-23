import { computed, ref } from "vue";

export const SHEET_DISMISS_PX = 72;

export function shouldDismissSheet(deltaY, threshold = SHEET_DISMISS_PX) {
	return deltaY >= threshold;
}

/**
 * Drag-down dismiss for the mobile context bottom sheet. Bind the pointer
 * handlers to the sheet chrome (not the scrolling body) so content still scrolls.
 */
export function useSheetDismiss(onClose) {
	const offsetY = ref(0);
	const dragging = ref(false);
	let startY = 0;

	function onPointerDown(e) {
		if (e.pointerType === "mouse" && e.button !== 0) return;
		startY = e.clientY;
		dragging.value = true;
		offsetY.value = 0;
		e.currentTarget?.setPointerCapture?.(e.pointerId);
	}

	function onPointerMove(e) {
		if (!dragging.value) return;
		offsetY.value = Math.max(0, e.clientY - startY);
	}

	function onPointerUp() {
		if (!dragging.value) return;
		const dy = offsetY.value;
		dragging.value = false;
		offsetY.value = 0;
		if (shouldDismissSheet(dy)) onClose();
	}

	const style = computed(() =>
		offsetY.value ? { transform: `translateY(${offsetY.value}px)` } : undefined,
	);

	return {
		offsetY,
		dragging,
		style,
		onPointerDown,
		onPointerMove,
		onPointerUp,
	};
}
