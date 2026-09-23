import { ref, onMounted, onBeforeUnmount } from "vue";

/** Keystrokes typed into a field belong to the field, not to the canvas. */
function isTypingTarget(target) {
	if (!target) return false;
	const tag = target.tagName;
	return (
		tag === "INPUT" ||
		tag === "TEXTAREA" ||
		tag === "SELECT" ||
		target.isContentEditable === true
	);
}

/**
 * A bounded undo history of graph snapshots.
 *
 * Snapshots are the same `vueFlowToGraphJson` strings the builder saves, so
 * restoring is exactly the load path — no separate inverse-operation model to
 * keep correct.
 */
export function createHistory({ limit = 50 } = {}) {
	const past = [];
	const future = [];
	let present = null;

	return {
		/** Seed the buffer without producing an undo step. */
		reset(snapshot) {
			past.length = 0;
			future.length = 0;
			present = snapshot ?? null;
		},
		/** Record a new state. No-ops when nothing actually changed. */
		record(snapshot) {
			if (snapshot === present) return;
			if (present !== null) {
				past.push(present);
				if (past.length > limit) past.shift();
			}
			present = snapshot;
			future.length = 0;
		},
		undo() {
			if (!past.length) return null;
			future.push(present);
			present = past.pop();
			return present;
		},
		redo() {
			if (!future.length) return null;
			past.push(present);
			present = future.pop();
			return present;
		},
		get canUndo() {
			return past.length > 0;
		},
		get canRedo() {
			return future.length > 0;
		},
		get current() {
			return present;
		},
	};
}

/**
 * Builder keyboard shortcuts.
 *
 * @param {object} handlers - { onSave, onUndo, onRedo, onDuplicate, onEscape,
 *                              onFitView, onOpenConfig, isEnabled }
 */
export function useBuilderShortcuts(handlers = {}) {
	const lastShortcut = ref("");

	function handleKeydown(event) {
		if (handlers.isEnabled && !handlers.isEnabled()) return;

		const mod = event.metaKey || event.ctrlKey;
		const typing = isTypingTarget(event.target);

		// Escape must work from inside a field — it is how you leave one.
		if (event.key === "Escape") {
			lastShortcut.value = "escape";
			handlers.onEscape?.();
			return;
		}

		if (typing) return;

		if (mod && event.key.toLowerCase() === "s") {
			event.preventDefault();
			lastShortcut.value = "save";
			handlers.onSave?.();
			return;
		}

		if (mod && event.key.toLowerCase() === "z") {
			event.preventDefault();
			if (event.shiftKey) {
				lastShortcut.value = "redo";
				handlers.onRedo?.();
			} else {
				lastShortcut.value = "undo";
				handlers.onUndo?.();
			}
			return;
		}

		if (mod && event.key.toLowerCase() === "d") {
			event.preventDefault();
			lastShortcut.value = "duplicate";
			handlers.onDuplicate?.();
			return;
		}

		if (!mod && event.key.toLowerCase() === "f") {
			lastShortcut.value = "fit-view";
			handlers.onFitView?.();
			return;
		}

		if (!mod && (event.key === "Enter" || event.key === " ")) {
			if (handlers.onOpenConfig?.()) {
				event.preventDefault();
				lastShortcut.value = "open-config";
			}
		}
	}

	onMounted(() => window.addEventListener("keydown", handleKeydown));
	onBeforeUnmount(() => window.removeEventListener("keydown", handleKeydown));

	return { handleKeydown, lastShortcut };
}
