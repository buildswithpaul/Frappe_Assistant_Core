import { describe, it, expect, vi } from "vitest";
import { createDeskVisibilityHandler } from "@/composables/useStreaming";

vi.mock("socket.io-client", () => ({ io: vi.fn() }));

function setVisible(v) {
	Object.defineProperty(document, "visibilityState", { value: v, configurable: true });
}

describe("Desk tab-visible recovery", () => {
	it("nudges a dead Desk socket and leaves recovery to its connect handler", () => {
		setVisible("visible");
		const socket = { connected: false, connect: vi.fn() };
		const recover = vi.fn();
		createDeskVisibilityHandler({ isStreaming: true }, () => socket, recover)();
		expect(socket.connect).toHaveBeenCalled();
		expect(recover).not.toHaveBeenCalled();
	});

	it("recovers an in-flight turn on a socket that still claims to be connected", () => {
		setVisible("visible");
		const recover = vi.fn();
		createDeskVisibilityHandler({ isStreaming: true }, () => ({ connected: true }), recover)();
		expect(recover).toHaveBeenCalled();
	});

	it("does nothing when the tab is hidden or nothing is streaming", () => {
		const recover = vi.fn();
		setVisible("hidden");
		createDeskVisibilityHandler({ isStreaming: true }, () => ({ connected: true }), recover)();
		setVisible("visible");
		createDeskVisibilityHandler({ isStreaming: false }, () => ({ connected: true }), recover)();
		expect(recover).not.toHaveBeenCalled();
	});
});
