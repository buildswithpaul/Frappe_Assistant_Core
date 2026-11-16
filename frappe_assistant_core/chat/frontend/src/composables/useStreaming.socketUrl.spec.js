import { describe, it, expect, vi } from "vitest";
import { spaSocketUrl } from "./useStreaming";

vi.mock("@/api/client", () => ({ api: { chat: { getMessages: vi.fn() }, get: vi.fn() } }));

const at = (href) => new URL(href);

describe("spaSocketUrl", () => {
	it("goes to the socketio port when bench start serves the site on its own port", () => {
		// copilot.py's boot sets window.dev_server and window.socketio_port under `bench start`
		const win = { dev_server: true, socketio_port: 9003, site_name: "test.local" };

		expect(spaSocketUrl(at("http://test.local:8003/copilot/chat"), win)).toBe(
			"http://test.local:9003/test.local",
		);
	});

	it("goes to the socketio port on localhost even without the flag", () => {
		expect(spaSocketUrl(at("http://localhost:8000/copilot"), { socketio_port: 9000, site_name: "s" })).toBe(
			"http://localhost:9000/s",
		);
	});

	it("stays on the page's own address behind nginx", () => {
		const win = { dev_server: false, socketio_port: 9000, site_name: "erp.example.com" };

		expect(spaSocketUrl(at("https://erp.example.com/copilot/chat"), win)).toBe(
			"https://erp.example.com/erp.example.com",
		);
		expect(spaSocketUrl(at("http://erp.example.com:8080/copilot/chat"), win)).toBe(
			"http://erp.example.com:8080/erp.example.com",
		);
	});
});
