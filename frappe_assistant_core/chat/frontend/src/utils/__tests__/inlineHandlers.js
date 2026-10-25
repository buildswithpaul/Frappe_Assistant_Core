// jsdom runs no page scripts, so it never compiles an inline handler. This does what a browser
// does when `type` reaches each element still carrying an on<type> attribute: run it as a handler.
export function fireInlineHandlers(root, type) {
	root.querySelectorAll(`[on${type}]`).forEach((el) => {
		new Function("event", el.getAttribute(`on${type}`)).call(el, new Event(type));
	});
}
