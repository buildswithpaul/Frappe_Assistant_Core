/**
 * Fail the widget build on the two things that silently break it in a shadow
 * root: a teleport to the page <body> (content escapes and loses its styles)
 * and Tailwind utilities (the widget ships no Tailwind).
 */
export const TAILWIND_ALLOWED = new Set(["w-3", "w-4", "w-5", "h-3", "h-4", "h-5"]);
const UTILITY =
	/^(flex|inline-flex|grid|hidden|truncate|shrink-0|items-[a-z]+|justify-[a-z]+|gap-\d+|space-[xy]-\d+|[pm][xytblr]?-[\d.]+|text-(xs|sm|base|lg|[2-9]?xl)|font-(medium|semibold|bold)|rounded(-[a-z]+)?|bg-[a-z]+-\d+|border(-[a-z0-9]+)?|[wh]-[\d/]+)$/;

export function findTeleportToBody(code) {
	return /<Teleport\s+to=["']body["']/.test(code);
}

export function findTailwindUtilities(code) {
	const found = [];
	for (const [, list] of code.matchAll(/\bclass="([^"]*)"/g)) {
		for (const token of list.split(/\s+/)) {
			if (token && UTILITY.test(token) && !TAILWIND_ALLOWED.has(token)) found.push(token);
		}
	}
	return found;
}

export function widgetGuards() {
	return {
		name: "fac-widget-guards",
		enforce: "pre",
		transform(code, id) {
			if (!id.endsWith(".vue")) return null;
			if (findTeleportToBody(code)) {
				this.error(`${id}: <Teleport to="body"> escapes the widget's shadow root — use useTeleportTarget()`);
			}
			const utilities = findTailwindUtilities(code);
			if (utilities.length) {
				this.error(`${id}: Tailwind classes the widget does not ship: ${utilities.join(", ")}`);
			}
			return null;
		},
	};
}
