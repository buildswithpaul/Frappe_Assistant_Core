/**
 * Where a document-level event came from, read through shadow roots.
 *
 * A click inside a shadow root (the Desk widget) reaches `document` with
 * `event.target` retargeted to the shadow host, so `target.closest()` and
 * `el.contains(target)` both miss. `composedPath()` keeps the real elements.
 */
function eventPath(event) {
	const path = event.composedPath?.();
	return path?.length ? path : [event.target];
}

/** True when the event passed through `el`. */
export function eventWithin(event, el) {
	return Boolean(el) && eventPath(event).includes(el);
}

/** True when the event passed through an element matching `selector`. */
export function eventMatches(event, selector) {
	return eventPath(event).some((node) => node instanceof Element && node.matches(selector));
}
