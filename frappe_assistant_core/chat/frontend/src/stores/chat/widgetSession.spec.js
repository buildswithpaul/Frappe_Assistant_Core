import { describe, it, expect, beforeAll } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const WIDGET_SESSION_PATH = resolve(
	here,
	"../../../../../public/chat/widget/widget_session.js"
);

let FACOWidgetSession;

beforeAll(() => {
	const source = readFileSync(WIDGET_SESSION_PATH, "utf8");
	new Function(source).call(globalThis);
	FACOWidgetSession = globalThis.FACOWidgetSession;
});

const generate = () => "faco_fresh_1";
const OWNER = "paul@x.test";
const OTHER = "administrator@x.test";
const entry = (id, user = OWNER) => ({ id, user });

describe("FACOWidgetSession.resolve", () => {
	it("adopts the persisted session when no other tab holds it", async () => {
		const result = await FACOWidgetSession.resolve({
			stored: null,
			persisted: entry("faco_persisted_1"),
			owner: OWNER,
			isClaimed: async () => false,
			generate,
		});
		expect(result.session_id).toBe("faco_persisted_1");
		expect(result.restored).toBe(true);
		expect(result.consumed_handoff).toBe(false);
	});

	it("mints a fresh session when another live tab holds the persisted id", async () => {
		const result = await FACOWidgetSession.resolve({
			stored: null,
			persisted: entry("faco_persisted_1"),
			owner: OWNER,
			isClaimed: async () => true,
			generate,
		});
		expect(result.session_id).toBe("faco_fresh_1");
		expect(result.restored).toBe(false);
	});

	it("mints a fresh session when a cloned SPA hand-off token is already held", async () => {
		const result = await FACOWidgetSession.resolve({
			stored: entry("faco_handoff_1"),
			persisted: null,
			owner: OWNER,
			isClaimed: async () => true,
			generate,
		});
		expect(result.session_id).toBe("faco_fresh_1");
		expect(result.restored).toBe(false);
		expect(result.consumed_handoff).toBe(true);
	});

	it("prefers the hand-off token over the persisted session", async () => {
		const result = await FACOWidgetSession.resolve({
			stored: entry("faco_handoff_1"),
			persisted: entry("faco_persisted_1"),
			owner: OWNER,
			isClaimed: async () => false,
			generate,
		});
		expect(result.session_id).toBe("faco_handoff_1");
		expect(result.consumed_handoff).toBe(true);
	});

	it("mints a fresh session when nothing is stored, without probing", async () => {
		let probed = false;
		const result = await FACOWidgetSession.resolve({
			stored: null,
			persisted: null,
			owner: OWNER,
			isClaimed: async () => {
				probed = true;
				return false;
			},
			generate,
		});
		expect(result.session_id).toBe("faco_fresh_1");
		expect(result.restored).toBe(false);
		expect(probed).toBe(false);
	});

	it("adopts rather than discards when the claim probe throws", async () => {
		const result = await FACOWidgetSession.resolve({
			stored: null,
			persisted: entry("faco_persisted_1"),
			owner: OWNER,
			isClaimed: async () => {
				throw new Error("BroadcastChannel unavailable");
			},
			generate,
		});
		expect(result.session_id).toBe("faco_persisted_1");
		expect(result.restored).toBe(true);
	});
});

/**
 * sessionStorage survives a logout and is cloned into duplicated tabs, and a
 * session id names no user of its own — so without an owner the next person to
 * log in continues the last person's conversation. One widget session id
 * really did accumulate eight turns under one user and two under another.
 */
describe("FACOWidgetSession.resolve — owner binding", () => {
	it("refuses a persisted session minted by a different user", async () => {
		const result = await FACOWidgetSession.resolve({
			stored: null,
			persisted: entry("faco_persisted_1", OTHER),
			owner: OWNER,
			isClaimed: async () => false,
			generate,
		});
		expect(result.session_id).toBe("faco_fresh_1");
		expect(result.restored).toBe(false);
	});

	it("refuses a SPA hand-off minted by a different user", async () => {
		const result = await FACOWidgetSession.resolve({
			stored: entry("faco_handoff_1", OTHER),
			persisted: null,
			owner: OWNER,
			isClaimed: async () => false,
			generate,
		});
		expect(result.session_id).toBe("faco_fresh_1");
		expect(result.restored).toBe(false);
	});

	it("still consumes a refused hand-off so it cannot be retried", async () => {
		const result = await FACOWidgetSession.resolve({
			stored: entry("faco_handoff_1", OTHER),
			persisted: null,
			owner: OWNER,
			isClaimed: async () => false,
			generate,
		});
		expect(result.consumed_handoff).toBe(true);
	});

	it("falls back to an owned persisted session when the hand-off is refused", async () => {
		const result = await FACOWidgetSession.resolve({
			stored: entry("faco_handoff_1", OTHER),
			persisted: entry("faco_persisted_1", OWNER),
			owner: OWNER,
			isClaimed: async () => false,
			generate,
		});
		expect(result.session_id).toBe("faco_persisted_1");
		expect(result.restored).toBe(true);
	});

	it("refuses a candidate stored without a recorded owner", async () => {
		// Values written before ownership was recorded could belong to anyone.
		// sessionStorage clears on tab close, so dropping them costs one reload.
		const result = await FACOWidgetSession.resolve({
			stored: null,
			persisted: entry("faco_legacy_1", null),
			owner: OWNER,
			isClaimed: async () => false,
			generate,
		});
		expect(result.session_id).toBe("faco_fresh_1");
		expect(result.restored).toBe(false);
	});

	it("refuses everything when the current user is unknown", async () => {
		const result = await FACOWidgetSession.resolve({
			stored: null,
			persisted: entry("faco_persisted_1", OWNER),
			owner: null,
			isClaimed: async () => false,
			generate,
		});
		expect(result.session_id).toBe("faco_fresh_1");
		expect(result.restored).toBe(false);
	});
});

describe("FACOWidgetSession.encode / decode", () => {
	it("round-trips an id with its owner", () => {
		const raw = FACOWidgetSession.encode("sess-a", OWNER);
		expect(FACOWidgetSession.decode(raw)).toEqual({ id: "sess-a", user: OWNER });
	});

	it("decodes a legacy bare-id value as not adoptable", () => {
		expect(FACOWidgetSession.decode("faco_1788368514319_1mp6h9vfs")).toBeNull();
	});

	it("decodes an absent value as nothing", () => {
		expect(FACOWidgetSession.decode(null)).toBeNull();
		expect(FACOWidgetSession.decode("")).toBeNull();
	});

	it("decodes a JSON value with no id as nothing", () => {
		expect(FACOWidgetSession.decode('{"user":"paul@x.test"}')).toBeNull();
	});

	it("writes a shape the SPA hand-off helper reads back", () => {
		// sessionHandoff.js in the SPA parses this exact envelope.
		expect(JSON.parse(FACOWidgetSession.encode("sess-a", OWNER))).toEqual({
			id: "sess-a",
			user: OWNER,
		});
	});
});
