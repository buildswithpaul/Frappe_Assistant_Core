import { describe, it, expect, beforeAll, beforeEach, afterEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import ConversationsList from "@/components/layout/ConversationsList.vue";
import { useChatStore } from "@/stores/chatStore";

beforeAll(() => {
	window.__ = (s) => s;
});

let observers;
beforeEach(() => {
	setActivePinia(createPinia());
	observers = [];
	// Production: the browser reports the sentinel as intersecting whenever observe() starts
	// watching it while it is in view; this stub models a sidebar tall enough that it stays in view.
	globalThis.IntersectionObserver = class {
		constructor(cb) {
			this.cb = cb;
			observers.push(this);
		}
		observe() {
			Promise.resolve().then(() => this.cb([{ isIntersecting: true }]));
		}
		disconnect() {}
	};
});
afterEach(() => {
	delete globalThis.IntersectionObserver;
});

describe("ConversationsList infinite scroll", () => {
	it("keeps loading while the sentinel stays visible and more pages exist", async () => {
		const chat = useChatStore();
		chat.sessionsHasMore = true;
		let pages = 0;
		chat.loadMoreSessions = vi.fn(async () => {
			pages += 1;
			chat.sessions = [...chat.sessions, { session_id: `s${pages}` }];
			chat.sessionsHasMore = pages < 2;
		});
		const w = mount(ConversationsList, {
			props: { sessions: [{ session_id: "s0", last_activity: new Date().toISOString() }] },
			global: { stubs: { ChatRow: true, ConversationSearch: true, ArchivedConversations: true } },
		});
		await flushPromises();
		await flushPromises();
		expect(chat.loadMoreSessions).toHaveBeenCalledTimes(2);
		w.unmount();
	});
});
