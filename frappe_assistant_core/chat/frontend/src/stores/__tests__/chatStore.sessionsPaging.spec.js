import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useChatStore, SESSIONS_PAGE_SIZE } from "@/stores/chatStore";
import { api } from "@/api/client";

vi.mock("@/api/client", () => ({
	api: { chat: { getSessions: vi.fn(), send: vi.fn().mockResolvedValue({}) } },
}));
vi.mock("frappe-ui", () => ({ call: vi.fn().mockResolvedValue({}) }));

const PENDING_SESSION = "brand-new";
const page = (n, start = 0) =>
	Array.from({ length: n }, (_, i) => ({ session_id: `s${start + i}`, last_activity: "2026-10-01" }));

describe("chatStore session paging", () => {
	let store;
	beforeEach(() => {
		setActivePinia(createPinia());
		store = useChatStore();
		vi.clearAllMocks();
	});

	it("loads the next page at the current offset and appends without duplicates", async () => {
		api.chat.getSessions.mockResolvedValueOnce(page(SESSIONS_PAGE_SIZE));
		await store.loadSessions();
		api.chat.getSessions.mockResolvedValueOnce([...page(1, SESSIONS_PAGE_SIZE - 1), ...page(3, SESSIONS_PAGE_SIZE)]);
		await store.loadMoreSessions();
		expect(api.chat.getSessions).toHaveBeenLastCalledWith({ limit: SESSIONS_PAGE_SIZE, offset: SESSIONS_PAGE_SIZE });
		expect(store.sessions).toHaveLength(SESSIONS_PAGE_SIZE + 3);
		expect(store.sessionsHasMore).toBe(false);
	});

	it("loadSessions resets sessionsHasMore from the fresh page", async () => {
		api.chat.getSessions.mockResolvedValueOnce(page(2));
		await store.loadSessions();
		expect(store.sessionsHasMore).toBe(false);
		api.chat.getSessions.mockResolvedValueOnce(page(SESSIONS_PAGE_SIZE));
		await store.loadSessions();
		expect(store.sessionsHasMore).toBe(true);
	});

	it("currentProjectId prefers the session row over a pending project", () => {
		store.sessions = [{ session_id: "a", project: null }];
		store.setPendingProject(PENDING_SESSION, "p1");
		store.currentSessionId = "a";
		expect(store.currentProjectId).toBe(null);
		store.currentSessionId = "brand-new";
		expect(store.currentProjectId).toBe("p1");
	});

	it("ignores a pending project that belongs to another session", () => {
		store.setPendingProject("brand-new", "p1");
		store.currentSessionId = "other";
		expect(store.currentProjectId).toBe(null);
	});

	it("inserts the conversation row the first send returns, without reloading", async () => {
		api.chat.getSessions.mockResolvedValueOnce(page(SESSIONS_PAGE_SIZE));
		await store.loadSessions();
		api.chat.getSessions.mockResolvedValueOnce(page(3, SESSIONS_PAGE_SIZE));
		await store.loadMoreSessions();
		api.chat.getSessions.mockClear();
		store.currentSessionId = "brand-new";
		const row = { session_id: "brand-new", last_activity: "2026-10-02", title: "hi" };
		api.chat.send.mockResolvedValueOnce({ status: "processing", conversation: row });
		await store.sendMessage("hi", [], null, "m1");
		expect(store.sessions[0]).toEqual(row);
		expect(store.sessions).toHaveLength(SESSIONS_PAGE_SIZE + 3 + 1);
		expect(store.sessions[SESSIONS_PAGE_SIZE + 3].session_id).toBe(`s${SESSIONS_PAGE_SIZE + 2}`);
		expect(store.sessionsHasMore).toBe(false);
		expect(api.chat.getSessions).not.toHaveBeenCalled();
		expect(store.isLoading).toBe(false);
		api.chat.send.mockResolvedValueOnce({ status: "processing", conversation: row });
		await store.sendMessage("again", [], null, "m1", null, { skipQueue: true });
		expect(store.sessions.filter((s) => s.session_id === "brand-new")).toHaveLength(1);
	});

	it("adds nothing when the ack carries no conversation (restricted user)", async () => {
		store.currentSessionId = "brand-new";
		api.chat.send.mockResolvedValueOnce({ status: "processing", conversation: null });
		await store.sendMessage("hi", [], null, "m1");
		expect(store.sessions).toEqual([]);
		expect(api.chat.getSessions).not.toHaveBeenCalled();
	});

	it("sends the current project with the message", async () => {
		store.currentSessionId = "brand-new";
		store.setPendingProject(PENDING_SESSION, "p1");
		await store.sendMessage("hi", [], null, "m1");
		expect(api.chat.send.mock.calls[0][7]).toMatchObject({ project: "p1" });
	});
});
