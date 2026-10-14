import { describe, it, expect, vi } from "vitest";
import { defineComponent, reactive, ref, nextTick } from "vue";
import { mount, flushPromises } from "@vue/test-utils";
import { useChatViewInit } from "./useChatViewInit";

function setup() {
	const calls = [];
	const chatStore = {
		loadMessages: vi.fn(async (id) => calls.push(`load:${id}`)),
		hydratePendingInterrupt: vi.fn(),
		takeFirstMessage: vi.fn((id) => (id === "s1" ? "hello" : null)),
		loadSessions: vi.fn(),
	};
	const route = reactive({ params: {}, query: {} });
	const onFirstMessage = vi.fn(async (text) => calls.push(`send:${text}`));
	const Host = defineComponent({
		setup() {
			// Not "ready": the mount branch stays out of the way, as for a user mid-onboarding.
			useChatViewInit(
				{ chatStore, userStore: {}, modelStore: {}, suggestionStore: {} },
				{ route, router: { push: vi.fn() } },
				{ registrationStatus: ref("pending"), isUserSetupComplete: ref(false) },
				{ onFirstMessage }
			);
			return () => null;
		},
	});
	mount(Host);
	return { route, calls, onFirstMessage };
}

describe("useChatViewInit first message", () => {
	it("sends the queued first message after the new session has loaded", async () => {
		const { route, calls, onFirstMessage } = setup();
		route.params.sessionId = "s1";
		await nextTick();
		await flushPromises();
		expect(calls).toEqual(["load:s1", "send:hello"]);
		expect(onFirstMessage).toHaveBeenCalledTimes(1);
	});

	it("sends nothing when no message is queued for the session", async () => {
		const { route, onFirstMessage } = setup();
		route.params.sessionId = "s2";
		await nextTick();
		await flushPromises();
		expect(onFirstMessage).not.toHaveBeenCalled();
	});
});
