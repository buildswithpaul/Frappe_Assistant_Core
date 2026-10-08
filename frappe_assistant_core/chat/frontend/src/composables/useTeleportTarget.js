import { inject } from "vue";

/**
 * Where modals and popovers teleport to. FAC Chat teleports to <body>; the
 * Desk widget lives in a shadow root, and anything teleported to the page's
 * <body> leaves it and loses every style, so the widget provides an overlay
 * container inside its shadow root.
 */
export const TELEPORT_TARGET_KEY = Symbol("fac-teleport-target");

export function useTeleportTarget() {
	return inject(TELEPORT_TARGET_KEY, "body");
}
