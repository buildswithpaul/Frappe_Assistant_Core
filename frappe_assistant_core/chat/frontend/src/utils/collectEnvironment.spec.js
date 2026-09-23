import { beforeEach, describe, expect, it, vi } from "vitest";

const getEnvironment = vi.fn();
vi.mock("@/api/client", () => ({ api: { support: { getEnvironment } } }));

describe("collectEnvironment", () => {
	let collectEnvironment;
	let loadServerEnvironment;

	beforeEach(async () => {
		vi.resetModules();
		getEnvironment.mockReset();
		({ collectEnvironment, loadServerEnvironment } = await import("./collectEnvironment"));
	});

	it("carries the server's versions through to the payload", () => {
		const env = collectEnvironment({ fac_version: "3.0.0", bench_version: "5.24.1" });
		expect(env.fac_version).toBe("3.0.0");
		expect(env.bench_version).toBe("5.24.1");
	});

	it("never invents an ar_version — AR is server-side", () => {
		expect(collectEnvironment({ fac_version: "3.0.0" })).not.toHaveProperty("ar_version");
	});

	it("adds the browser half the server can't know", () => {
		const env = collectEnvironment();
		expect(env.browser).toBe(navigator.userAgent);
		expect(env.language).toBe(navigator.language);
	});

	it("lets extras win over server keys", () => {
		const env = collectEnvironment({ model: "stale" }, { model: "claude-opus-5" });
		expect(env.model).toBe("claude-opus-5");
	});

	it("fetches the server half once, however many times it's asked", async () => {
		getEnvironment.mockResolvedValue({ fac_version: "3.0.0" });
		const [a, b] = await Promise.all([loadServerEnvironment(), loadServerEnvironment()]);
		expect(a).toEqual({ fac_version: "3.0.0" });
		expect(b).toEqual({ fac_version: "3.0.0" });
		expect(getEnvironment).toHaveBeenCalledTimes(1);
	});

	it("still lets the user file a report when versions can't be fetched", async () => {
		getEnvironment.mockRejectedValue(new Error("offline"));
		await expect(loadServerEnvironment()).resolves.toEqual({});
	});
});
