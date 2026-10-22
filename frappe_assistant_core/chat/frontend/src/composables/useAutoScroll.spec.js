import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ref, nextTick } from "vue";
import { mount } from "@vue/test-utils";
import { useAutoScroll } from "./useAutoScroll.js";

function withSetup(fn) {
	let result;
	const wrapper = mount({
		setup() {
			result = fn();
			return () => null;
		},
	});
	return { result, wrapper };
}

describe("useAutoScroll API", () => {
	it("exposes isFollowing and scrollToBottom", () => {
		const el = { scrollTop: 0, scrollHeight: 500, clientHeight: 200, addEventListener() {}, removeEventListener() {} };
		const { result } = withSetup(() =>
			useAutoScroll(ref(el), ref([]), ref(false))
		);
		expect(result.isFollowing.value).toBe(true);
		result.scrollToBottom();
		expect(el.scrollTop).toBe(500);
	});
});

describe("useAutoScroll on a new chat", () => {
	it("shows the emptied list's welcome from the top, not scrolled to the bottom", async () => {
		const el = { scrollTop: 300, scrollHeight: 500, clientHeight: 200, addEventListener() {}, removeEventListener() {} };
		const messages = ref([{ role: "user", content: "hi" }]);
		withSetup(() => useAutoScroll(ref(el), messages, ref(false)));
		messages.value = [];
		await nextTick();
		await nextTick();
		expect(el.scrollTop).toBe(0);
	});
});

// jsdom has no layout, so the observer is replaced with one the test triggers by hand; on a
// device ResizeObserver fires when a tool card or plan lands, or the keyboard shrinks the list.
describe("useAutoScroll when the layout changes without a scroll event", () => {
	let fire;
	beforeEach(() => {
		fire = null;
		vi.stubGlobal(
			"ResizeObserver",
			class {
				constructor(cb) {
					fire = cb;
				}
				observe() {}
				disconnect() {}
			}
		);
	});
	afterEach(() => vi.unstubAllGlobals());

	function scroller({ scrollTop, scrollHeight, clientHeight }) {
		const el = document.createElement("div");
		el.appendChild(document.createElement("div"));
		let height = scrollHeight;
		el.scrollTop = scrollTop;
		Object.defineProperty(el, "scrollHeight", { get: () => height });
		Object.defineProperty(el, "clientHeight", { get: () => clientHeight });
		// jsdom clamps nothing, so record writes directly.
		let top = scrollTop;
		Object.defineProperty(el, "scrollTop", { get: () => top, set: (v) => (top = v) });
		return { el, grow: (h) => (height = h) };
	}

	it("keeps a follower on the latest line when a block grows the answer", async () => {
		const { el, grow } = scroller({ scrollTop: 300, scrollHeight: 500, clientHeight: 200 });
		const messages = ref([{ role: "assistant", content: "Plan", isStreaming: true }]);
		withSetup(() => useAutoScroll(ref(el), messages, ref(true)));
		grow(900); // a tool card arrived; the text length did not change
		fire([]);
		expect(el.scrollTop).toBe(900);
	});

	it("re-pins the last answer when the keyboard shrinks the list", async () => {
		const { el } = scroller({ scrollTop: 300, scrollHeight: 500, clientHeight: 200 });
		const messages = ref([{ role: "assistant", content: "Done" }]);
		withSetup(() => useAutoScroll(ref(el), messages, ref(false)));
		fire([]);
		expect(el.scrollTop).toBe(500);
	});

	it("leaves a reader who scrolled up where they are", async () => {
		const { el, grow } = scroller({ scrollTop: 300, scrollHeight: 500, clientHeight: 200 });
		const messages = ref([{ role: "assistant", content: "Plan", isStreaming: true }]);
		withSetup(() => useAutoScroll(ref(el), messages, ref(true)));
		el.scrollTop = 0;
		el.dispatchEvent(new Event("scroll"));
		grow(900);
		fire([]);
		expect(el.scrollTop).toBe(0);
	});

	it("does not scroll the new-chat welcome", async () => {
		const { el } = scroller({ scrollTop: 0, scrollHeight: 900, clientHeight: 200 });
		withSetup(() => useAutoScroll(ref(el), ref([]), ref(false)));
		fire([]);
		expect(el.scrollTop).toBe(0);
	});
});
