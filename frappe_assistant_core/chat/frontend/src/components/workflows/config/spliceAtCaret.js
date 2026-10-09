/** Inserts text at the textarea caret, replacing any selection; appends when there is no element. */
export function spliceAtCaret(current, insertion, el) {
	const start = el?.selectionStart ?? current.length;
	const end = el?.selectionEnd ?? current.length;
	return current.slice(0, start) + insertion + current.slice(end);
}
