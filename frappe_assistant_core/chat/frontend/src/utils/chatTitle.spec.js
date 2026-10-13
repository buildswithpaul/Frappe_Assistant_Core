import { describe, it, expect, beforeAll } from "vitest";
import { chatDisplayTitle, chatRenameSeed } from "@/utils/chatTitle";

beforeAll(() => {
	window.__ = (s) => s;
});

const untitled = { session_id: "a", title: "", preview: "New conversation" };
const long = "a".repeat(80);

describe("chatTitle", () => {
	it("seeds an untitled row with an empty string, not the server placeholder", () => {
		expect(chatRenameSeed(untitled)).toBe("");
		expect(chatRenameSeed(null)).toBe("");
	});

	it("keeps an 80-char title whole in both the display title and the seed", () => {
		const row = { session_id: "b", title: long, preview: long };
		expect(chatDisplayTitle(row, true)).toBe(long);
		expect(chatRenameSeed(row)).toBe(long);
	});

	it("displays the preview when there is no title", () => {
		expect(chatDisplayTitle(untitled, true)).toBe("New conversation");
	});

	it("falls back to Chat / New Chat with no session", () => {
		expect(chatDisplayTitle(null, true)).toBe("Chat");
		expect(chatDisplayTitle(null, false)).toBe("New Chat");
	});
});
