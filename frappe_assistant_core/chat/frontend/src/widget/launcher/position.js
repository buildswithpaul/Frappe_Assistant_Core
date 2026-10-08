import { bridge } from "../bridge.js";

const STORAGE_KEY = "faco_custom_position";
const DRAG_THRESHOLD = 5;

let customPosition = null;
let hasDragged = false;

/** True once after a drag, so the click that ends the drag does not toggle the panel. */
export function consumeDrag() {
	const dragged = hasDragged;
	hasDragged = false;
	return dragged;
}

function loadCustomPosition() {
	try {
		const saved = localStorage.getItem(STORAGE_KEY);
		return saved ? JSON.parse(saved) : null;
	} catch {
		return null;
	}
}

function saveCustomPosition(widgetEl, left, top) {
	try {
		const viewportWidth = window.innerWidth;
		const viewportHeight = window.innerHeight;
		const rect = widgetEl.getBoundingClientRect();
		const anchorRight = left + rect.width / 2 > viewportWidth / 2;
		const anchorBottom = top + rect.height / 2 > viewportHeight / 2;
		customPosition = {
			anchorRight,
			anchorBottom,
			offsetX: anchorRight ? viewportWidth - left - rect.width : left,
			offsetY: anchorBottom ? viewportHeight - top - rect.height : top,
		};
		localStorage.setItem(STORAGE_KEY, JSON.stringify(customPosition));
	} catch {
		// Storage disabled: the position holds for this page load only.
	}
}

/** Accepts the anchor-based format or, for old saves, absolute (left, top) pixels. */
function applyCustomPosition(widgetEl, leftOrPosition, top) {
	if (typeof leftOrPosition === "object" && leftOrPosition !== null) {
		const p = leftOrPosition;
		const css = { position: "fixed" };
		if (p.anchorRight) {
			css.right = p.offsetX + "px";
			css.left = "auto";
		} else {
			css.left = p.offsetX + "px";
			css.right = "auto";
		}
		if (p.anchorBottom) {
			css.bottom = p.offsetY + "px";
			css.top = "auto";
		} else {
			css.top = p.offsetY + "px";
			css.bottom = "auto";
		}
		Object.assign(widgetEl.style, css);
	} else {
		Object.assign(widgetEl.style, {
			position: "fixed",
			left: leftOrPosition + "px",
			top: top + "px",
			right: "auto",
			bottom: "auto",
		});
	}
}

function constrainToViewport(widgetEl) {
	const rect = widgetEl.getBoundingClientRect();
	let left = rect.left;
	let top = rect.top;
	let needsUpdate = false;

	if (rect.right > window.innerWidth) {
		left = Math.max(0, window.innerWidth - rect.width);
		needsUpdate = true;
	}
	if (rect.bottom > window.innerHeight) {
		top = Math.max(0, window.innerHeight - rect.height);
		needsUpdate = true;
	}
	if (rect.left < 0) {
		left = 0;
		needsUpdate = true;
	}
	if (rect.top < 0) {
		top = 0;
		needsUpdate = true;
	}
	if (needsUpdate) {
		applyCustomPosition(widgetEl, left, top);
		saveCustomPosition(widgetEl, left, top);
	}
}

function setupResizeHandler(widgetEl) {
	let timer;
	window.addEventListener("resize", () => {
		clearTimeout(timer);
		timer = setTimeout(() => {
			if (customPosition && customPosition.anchorRight !== undefined) {
				applyCustomPosition(widgetEl, customPosition);
			}
			constrainToViewport(widgetEl);
		}, 100);
	});
}

export function restorePosition(widgetEl) {
	customPosition = loadCustomPosition();
	if (customPosition) {
		if (customPosition.anchorRight !== undefined) {
			applyCustomPosition(widgetEl, customPosition);
		} else if (customPosition.left !== undefined) {
			applyCustomPosition(widgetEl, customPosition.left, customPosition.top);
		}
	}
	setupResizeHandler(widgetEl);
}

export function enableDrag(widgetEl, button) {
	let dragging = false;
	let startX, startY, startLeft, startTop;

	button.style.cursor = "grab";

	button.addEventListener("mousedown", (e) => {
		if (bridge.state.open) return;
		dragging = true;
		hasDragged = false;
		const rect = widgetEl.getBoundingClientRect();
		startX = e.clientX;
		startY = e.clientY;
		startLeft = rect.left;
		startTop = rect.top;
		button.style.cursor = "grabbing";
		widgetEl.classList.add("faco-dragging");
		e.preventDefault();
	});

	document.addEventListener("mousemove", (e) => {
		if (!dragging) return;
		const dx = e.clientX - startX;
		const dy = e.clientY - startY;
		if (Math.abs(dx) > DRAG_THRESHOLD || Math.abs(dy) > DRAG_THRESHOLD) hasDragged = true;

		const rect = widgetEl.getBoundingClientRect();
		const left = Math.max(0, Math.min(startLeft + dx, window.innerWidth - rect.width));
		const top = Math.max(0, Math.min(startTop + dy, window.innerHeight - rect.height));
		applyCustomPosition(widgetEl, left, top);
	});

	document.addEventListener("mouseup", () => {
		if (!dragging) return;
		dragging = false;
		button.style.cursor = "grab";
		widgetEl.classList.remove("faco-dragging");
		if (hasDragged) {
			const rect = widgetEl.getBoundingClientRect();
			saveCustomPosition(widgetEl, rect.left, rect.top);
		}
	});
}
