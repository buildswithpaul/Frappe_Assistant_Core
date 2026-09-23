import { ref } from "vue";

export const ERROR_AUTO_DISMISS_MS = 8000;

/**
 * Error banner state with auto-dismiss. Every setError arms a fresh timer,
 * so the banner disappears a few seconds after the LAST error instead of
 * persisting until manually dismissed.
 */
export function createErrorState({ autoDismissMs = ERROR_AUTO_DISMISS_MS } = {}) {
	const error = ref(null);
	const errorCode = ref(null);
	let dismissTimer = null;

	function clearError() {
		clearTimeout(dismissTimer);
		dismissTimer = null;
		error.value = null;
		errorCode.value = null;
	}

	function setError(message, code = null) {
		error.value = message;
		errorCode.value = code;
		clearTimeout(dismissTimer);
		dismissTimer = setTimeout(clearError, autoDismissMs);
	}

	return { error, errorCode, setError, clearError };
}
