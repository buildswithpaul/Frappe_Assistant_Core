/**
 * Toast notification composable.
 *
 * Provides a reactive toast queue with auto-dismiss.
 * Usage: const { showToast, showError, showSuccess } = useToast()
 */

import { ref } from "vue";

const toasts = ref([]);
let nextId = 0;

export function useToast() {
	/** Returns the toast's id, so a `duration` of 0 can be dismissed later. */
	function showToast(message, type = "info", duration = 3000) {
		const id = nextId++;
		toasts.value.push({ id, message, type });

		if (duration > 0) {
			setTimeout(() => {
				dismiss(id);
			}, duration);
		}
		return id;
	}

	function showError(message) {
		showToast(message, "error", 5000);
	}

	function showSuccess(message) {
		showToast(message, "success", 3000);
	}

	function dismiss(id) {
		toasts.value = toasts.value.filter((t) => t.id !== id);
	}

	return { toasts, showToast, showError, showSuccess, dismiss };
}
