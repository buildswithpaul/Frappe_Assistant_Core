import { describe, it, expect } from "vitest";
import { ref } from "vue";
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
