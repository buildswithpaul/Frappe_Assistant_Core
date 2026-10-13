import { nextTick, ref } from "vue";

export const TITLE_MAX_LENGTH = 140;

/**
 * State for a click-to-rename title. `commit` returns early unless editing, so the
 * blur fired when Enter/Escape unmounts the input cannot save a second time (or save
 * a title the user just cancelled): both paths clear `editing` before the unmount.
 */
export function useInlineTitleEdit(getValue, onCommit) {
	const editing = ref(false);
	const draft = ref("");
	const inputRef = ref(null);

	async function start() {
		draft.value = getValue() || "";
		editing.value = true;
		await nextTick();
		inputRef.value?.focus();
		inputRef.value?.select();
	}

	function commit() {
		if (!editing.value) return;
		editing.value = false;
		onCommit(draft.value.trim().split(/\s+/).join(" "));
	}

	function cancel() {
		editing.value = false;
	}

	return { editing, draft, inputRef, start, commit, cancel };
}
