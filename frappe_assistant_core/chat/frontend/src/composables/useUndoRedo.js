/**
 * Undo/redo composable for graph state history.
 *
 * Maintains a stack of serialized state snapshots.
 * Usage:
 *   const { snapshot, undo, redo, canUndo, canRedo } = useUndoRedo()
 *   snapshot({ nodes, edges })  // after each change
 *   undo()  // returns previous state
 *   redo()  // returns next state
 */

import { ref, computed } from "vue";

export function useUndoRedo(maxHistory = 50) {
	const history = ref([]);
	const pointer = ref(-1);

	const canUndo = computed(() => pointer.value > 0);
	const canRedo = computed(() => pointer.value < history.value.length - 1);

	/**
	 * Take a snapshot of the current state.
	 * Clears any future states (redo stack) after the current pointer.
	 */
	function snapshot(state) {
		const serialized = JSON.stringify(state);

		// Skip if identical to current state (avoid duplicate snapshots)
		if (pointer.value >= 0 && history.value[pointer.value] === serialized) {
			return;
		}

		// Truncate future states
		history.value = history.value.slice(0, pointer.value + 1);

		// Add new state
		history.value.push(serialized);

		// Trim oldest entries if over max
		if (history.value.length > maxHistory) {
			history.value = history.value.slice(history.value.length - maxHistory);
		}

		pointer.value = history.value.length - 1;
	}

	/**
	 * Move back one step. Returns the parsed state or null.
	 */
	function undo() {
		if (!canUndo.value) return null;
		pointer.value--;
		return JSON.parse(history.value[pointer.value]);
	}

	/**
	 * Move forward one step. Returns the parsed state or null.
	 */
	function redo() {
		if (!canRedo.value) return null;
		pointer.value++;
		return JSON.parse(history.value[pointer.value]);
	}

	/**
	 * Clear all history.
	 */
	function clear() {
		history.value = [];
		pointer.value = -1;
	}

	return { snapshot, undo, redo, canUndo, canRedo, clear };
}
