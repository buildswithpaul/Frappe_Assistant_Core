import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/utils/logger", () => ({ logger: { error: vi.fn(), debug: vi.fn() } }));

import { chat } from "./chat";

describe("chat.uploadFile", () => {
	afterEach(() => vi.unstubAllGlobals());

	it("says the file is over the site's limit when Frappe refuses it as too large (#33987)", async () => {
		// Frappe's own 413 page: HTML, no message for the user in it
		const page = "<!doctype html><title>413 Request Entity Too Large</title>";
		vi.stubGlobal(
			"fetch",
			vi.fn().mockResolvedValue({ ok: false, status: 413, text: async () => page })
		);

		await expect(chat.uploadFile(new File(["x"], "big.csv"))).rejects.toThrow(
			"The file is larger than this site's upload limit."
		);
	});
});
