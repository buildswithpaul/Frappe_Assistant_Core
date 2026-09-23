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
	function showToast(message, type = "info", duration = 3000) {
		const id = nextId++;
		toasts.value.push({ id, message, type });

		if (duration > 0) {
			setTimeout(() => {
				dismiss(id);
			}, duration);
		}
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
