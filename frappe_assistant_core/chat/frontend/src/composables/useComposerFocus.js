import { onBeforeUnmount, onMounted } from "vue";

export const COMPOSER_FOCUSED_CLASS = "ql-composer-focused";

const isComposer = (el) => Boolean(el?.classList?.contains("input-textarea"));

/**
 * Mousedown handler for the composer: pressing one of its buttons keeps focus where it is.
 *
 * Otherwise the text box loses focus on the press, the phone layout below collapses under
 * the finger, and the click lands on whatever moved there: Send took two taps (#34382).
 * Checking `relatedTarget` on blur would not help, because Safari never focuses a tapped
 * button, so it is always null there. Tab and Enter never fire mousedown, so keyboard use
 * of the buttons is unchanged.
 */
export function keepComposerFocus(event) {
	if (event.target?.closest?.("button")) event.preventDefault();
}

/**
 * Mark the page while the chat composer has focus, so small screens can give the conversation
 * the room a phone keyboard takes: TopBar, App and InputArea collapse their chrome under
 * `html.ql-composer-focused` in a max-width media query. Desktop styles never read the class.
 *
 * iOS does not resize the layout for its keyboard; it scrolls the document to the field
 * instead, and the shell then shrinks to the visual viewport (useVisualViewportFrame). A
 * composer inside the scrolling list (the new-chat welcome) can end up below the shrunk
 * shell, so it is scrolled back into view whenever the visible viewport changes.
 */
export function useComposerFocus() {
	const root = document.documentElement;

	function onFocusIn(event) {
		if (isComposer(event.target)) root.classList.add(COMPOSER_FOCUSED_CLASS);
	}

	function onFocusOut(event) {
		if (isComposer(event.target)) root.classList.remove(COMPOSER_FOCUSED_CLASS);
	}

	function onViewportResize() {
		const active = document.activeElement;
		if (!isComposer(active)) return;
		// The whole composer, so its send button comes into view with the text box.
		(active.closest(".input-box") || active).scrollIntoView({ block: "nearest" });
	}

	onMounted(() => {
		document.addEventListener("focusin", onFocusIn);
		document.addEventListener("focusout", onFocusOut);
		window.visualViewport?.addEventListener("resize", onViewportResize);
	});

	onBeforeUnmount(() => {
		document.removeEventListener("focusin", onFocusIn);
		document.removeEventListener("focusout", onFocusOut);
		window.visualViewport?.removeEventListener("resize", onViewportResize);
		root.classList.remove(COMPOSER_FOCUSED_CLASS);
	});
}
