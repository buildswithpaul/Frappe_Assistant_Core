import { onMounted, onBeforeUnmount } from "vue";

/**
 * Warn on browser close/reload when a dirty flag is set. The browser's native
 * "leave site?" dialog fires via the beforeunload event's returnValue.
 *
 * @param {import('vue').Ref<boolean>} isDirty - reactive dirty flag
 */
export function useUnsavedGuard(isDirty) {
	function warnUnsaved(e) {
		if (isDirty.value) {
			e.preventDefault();
			e.returnValue = "";
		}
	}

	onMounted(() => {
		window.addEventListener("beforeunload", warnUnsaved);
	});

	onBeforeUnmount(() => {
		window.removeEventListener("beforeunload", warnUnsaved);
	});
}
