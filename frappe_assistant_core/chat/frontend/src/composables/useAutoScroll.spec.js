import { describe, it, expect } from "vitest";
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
