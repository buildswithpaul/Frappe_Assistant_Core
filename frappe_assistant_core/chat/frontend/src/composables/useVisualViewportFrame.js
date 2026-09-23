import { onBeforeUnmount, onMounted, unref, watch } from "vue";

/**
 * Size a fixed shell to the *visible* viewport (URL bar, iPadOS chrome, and
 * the on-screen keyboard). CSS 100vh / even 100dvh still overshoots on tablet
 * Safari, which is how the chat composer ends up below the fold in tab mode.
 *
 * `applyVisualViewportFrame` is exported for unit tests.
 */
export function applyVisualViewportFrame(el, viewport, innerHeight) {
	if (!el) return;
	if (!viewport) {
		el.style.top = "";
		el.style.left = "";
		el.style.width = "";
		el.style.height = "";
		el.style.right = "";
		el.style.bottom = "";
		return;
	}
	const cap = innerHeight ?? viewport.height;
	const height = Math.min(viewport.height, cap);
	el.style.top = `${viewport.offsetTop}px`;
	el.style.left = `${viewport.offsetLeft}px`;
	el.style.width = `${viewport.width}px`;
	el.style.height = `${height}px`;
	el.style.right = "auto";
	el.style.bottom = "auto";
}

export function useVisualViewportFrame(elRef) {
	function sync() {
		applyVisualViewportFrame(unref(elRef), window.visualViewport, window.innerHeight);
	}

	onMounted(() => {
		sync();
		window.visualViewport?.addEventListener("resize", sync);
		window.visualViewport?.addEventListener("scroll", sync);
		window.addEventListener("resize", sync);
	});

	onBeforeUnmount(() => {
		window.visualViewport?.removeEventListener("resize", sync);
		window.visualViewport?.removeEventListener("scroll", sync);
		window.removeEventListener("resize", sync);
	});

	watch(elRef, () => sync());
}
