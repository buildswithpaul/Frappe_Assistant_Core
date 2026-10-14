import { describe, it, expect, beforeAll } from "vitest";
import { projectDeleteMessage } from "@/utils/projectDeleteMessage";

beforeAll(() => {
	window.__ = (s) => s;
});

describe("projectDeleteMessage", () => {
	it.each([
		[
			true,
			true,
			"Delete this project? Its chats are kept, its documents move to your Knowledge Base as private documents, and its memories are deleted.",
		],
		[
			true,
			false,
			"Delete this project? Its chats are kept and its documents move to your Knowledge Base as private documents.",
		],
		[false, true, "Delete this project? Its chats are kept and its memories are deleted."],
		[false, false, "Delete this project? Its chats are kept and moved out of the project."],
	])("documents=%s memory=%s", (documents, memory, expected) => {
		expect(projectDeleteMessage({ documents, memory })).toBe(expected);
	});
});
