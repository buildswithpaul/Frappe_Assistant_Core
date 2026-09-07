import { describe, it, expect, beforeEach } from "vitest";
import { readHandoff, writeHandoff } from "./sessionHandoff";

/**
 * The SPA and the desk widget hand a session id to each other through
 * sessionStorage, which survives a logout and is cloned into duplicated tabs.
 * Both ends stamp the id with the user who minted it and refuse to adopt one
 * minted by anybody else — this is the SPA half of the shape implemented in
 * public/chat/widget/widget_session.js.
 */
const KEY = "faco_active_session";

beforeEach(() => {
	sessionStorage.clear();
});

describe("session hand-off", () => {
	it("reads back an id written by the same user", () => {
		writeHandoff(KEY, "sess-a", "paul@x.test");
		expect(readHandoff(KEY, "paul@x.test")).toBe("sess-a");
	});

	it("refuses an id written by a different user", () => {
		writeHandoff(KEY, "sess-a", "administrator@x.test");
		expect(readHandoff(KEY, "paul@x.test")).toBeNull();
	});

	it("refuses a legacy bare-id value", () => {
		sessionStorage.setItem(KEY, "faco_1788368514319_1mp6h9vfs");
		expect(readHandoff(KEY, "paul@x.test")).toBeNull();
	});

	it("refuses everything when the current user is unknown", () => {
		writeHandoff(KEY, "sess-a", "paul@x.test");
		expect(readHandoff(KEY, null)).toBeNull();
	});

	it("reads an absent key as nothing", () => {
		expect(readHandoff(KEY, "paul@x.test")).toBeNull();
	});

	it("writes nothing when there is no id to hand off", () => {
		writeHandoff(KEY, null, "paul@x.test");
		expect(sessionStorage.getItem(KEY)).toBeNull();
	});

	it("stores a shape the widget can decode", () => {
		writeHandoff(KEY, "sess-a", "paul@x.test");
		expect(JSON.parse(sessionStorage.getItem(KEY))).toEqual({
			id: "sess-a",
			user: "paul@x.test",
		});
	});
});
