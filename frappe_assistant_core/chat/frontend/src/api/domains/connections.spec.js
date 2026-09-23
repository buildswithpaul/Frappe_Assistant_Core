import { beforeEach, describe, expect, it, vi } from "vitest";

const baseCall = vi.fn();
const getCall = vi.fn();

vi.mock("../_core", () => ({
	baseCall: (...args) => baseCall(...args),
	getCall: (...args) => getCall(...args),
}));

import { connections } from "./connections";

const BASE = "frappe_assistant_core.chat.api.connections";

describe("connections connect-wizard calls", () => {
	beforeEach(() => {
		baseCall.mockReset().mockResolvedValue({});
		getCall.mockReset().mockResolvedValue({});
	});

	it("beginConnect posts the endpoint URL", async () => {
		await connections.beginConnect("https://acme.example/mcp");
		expect(baseCall).toHaveBeenCalledWith(`${BASE}.begin_connect`, {
			endpoint_url: "https://acme.example/mcp",
			client_id: null,
			client_secret: null,
		});
	});

	it("beginConnect forwards manual credentials when given", async () => {
		await connections.beginConnect("https://acme.example/mcp", "cid", "secret");
		expect(baseCall).toHaveBeenCalledWith(`${BASE}.begin_connect`, {
			endpoint_url: "https://acme.example/mcp",
			client_id: "cid",
			client_secret: "secret",
		});
	});

	it("getConnectSession reads over GET, not POST", async () => {
		// The endpoint is declared methods=["GET"]. Posting it would 404 at
		// Frappe's router.
		await connections.getConnectSession("h-1");
		expect(getCall).toHaveBeenCalledWith(`${BASE}.get_connect_session`, { handle: "h-1" });
		expect(baseCall).not.toHaveBeenCalled();
	});

	it("commitConnect posts the handle and the chosen name", async () => {
		await connections.commitConnect("h-1", "Acme");
		expect(baseCall).toHaveBeenCalledWith(`${BASE}.commit_connect`, {
			handle: "h-1",
			server_name: "Acme",
		});
	});

	it("abandonConnect posts the handle", async () => {
		await connections.abandonConnect("h-1");
		expect(baseCall).toHaveBeenCalledWith(`${BASE}.abandon_connect`, { handle: "h-1" });
	});

	it("beginReauth posts the server name to the reauth endpoint", async () => {
		// Not begin_connect: the reauth endpoint is what sets reauth_target, and
		// that is what lets commit update the existing row instead of failing
		// the duplicate-name guard.
		await connections.beginReauth("Acme");
		expect(baseCall).toHaveBeenCalledWith(`${BASE}.begin_reauth`, { server_name: "Acme" });
	});
});
