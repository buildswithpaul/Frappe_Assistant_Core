import { describe, it, expect, vi, beforeEach } from "vitest";

describe("ensurePanel", () => {
	let ensurePanel;

	beforeEach(async () => {
		vi.resetModules();
		({ ensurePanel } = await import("./panelLoader.js"));
	});

	it("retries after a failed import and mounts the panel exactly once", async () => {
		const panel = { open() {}, close() {} };
		const mountPanel = vi.fn(async () => panel);
		const load = vi
			.fn()
			.mockRejectedValueOnce(new Error("chunk failed"))
			.mockResolvedValue({ mountPanel });

		await expect(ensurePanel({}, load)).rejects.toThrow("chunk failed");
		await expect(ensurePanel({}, load)).resolves.toBe(panel);
		await expect(ensurePanel({}, load)).resolves.toBe(panel);
		expect(mountPanel).toHaveBeenCalledTimes(1);
		expect(load).toHaveBeenCalledTimes(2);
	});

	it("retries when mountPanel itself rejects", async () => {
		const panel = { open() {}, close() {} };
		const mountPanel = vi.fn().mockRejectedValueOnce(new Error("mount failed")).mockResolvedValue(panel);
		const load = async () => ({ mountPanel });

		await expect(ensurePanel({}, load)).rejects.toThrow("mount failed");
		await expect(ensurePanel({}, load)).resolves.toBe(panel);
	});
});
