import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";

// jsdom implements no navigation: window.location.assign logs "Not
// implemented" and the page never moves, so leaveForAuth is unassertable
// unless it is stubbed. Only `assign` is ever read by the component.
const navigateTo = vi.fn();

const beginConnect = vi.fn();
const getConnectSession = vi.fn();
const commitConnect = vi.fn();
const abandonConnect = vi.fn();
const beginReauth = vi.fn();

vi.mock("@/api/client", () => {
	const api = {
		connections: {
			beginConnect: (...a) => beginConnect(...a),
			getConnectSession: (...a) => getConnectSession(...a),
			commitConnect: (...a) => commitConnect(...a),
			abandonConnect: (...a) => abandonConnect(...a),
			beginReauth: (...a) => beginReauth(...a),
		},
	};
	return { api, default: api };
});

import ConnectWizard from "./ConnectWizard.vue";

const PREFLIGHT_OAUTH = {
	steps: [
		{ key: "url_shape", label: "URL shape", status: "pass", detail: "https", next_action: null },
		{ key: "speaks_mcp", label: "Speaks MCP", status: "pass", detail: "2025-06-18", next_action: null },
	],
	server_info: { name: "Acme Tasks", version: "2.1.0", protocol_version: "2025-06-18" },
	auth: {
		scheme: "oauth",
		authorization_server: "https://auth.acme.example",
		supports_dcr: true,
		scopes: ["tasks.read"],
		issuer: "https://auth.acme.example",
	},
};

const CAPS = { tools: [{ name: "create_task" }], resources: [], prompts: [], tool_count: 1, est_tokens: 240 };

// stepDelayMs: 0 reveals every row synchronously, so tests assert on final
// state rather than racing a timer.
const mountWizard = (props = {}) =>
	mount(ConnectWizard, { props: { stepDelayMs: 0, ...props } });

async function check(w, url = "https://acme.example/mcp") {
	await w.find('[data-test="endpoint-url"]').setValue(url);
	// jsdom does not fire a form's submit event from a real button click
	// unless the form is attached to `document` (see FeedbackForm.spec.js for
	// the same repo-wide workaround) — trigger "submit" on the form directly
	// so this exercises the same @submit.prevent="start()" handler.
	await w.find("form").trigger("submit");
	await flushPromises();
}

describe("ConnectWizard entry and checking", () => {
	beforeEach(() => {
		beginConnect.mockReset();
		getConnectSession.mockReset();
		commitConnect.mockReset().mockResolvedValue({ success: true });
		abandonConnect.mockReset().mockResolvedValue({ success: true });
		beginReauth.mockReset();
		// No browser storage to reset: reauth mode is read off the session
		// payload's reauth_server_name, so nothing about it survives in this tab.
		navigateTo.mockReset();
		vi.stubGlobal("location", {
			href: "https://fac.example/copilot/settings/connections",
			assign: navigateTo,
		});
	});

	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it("opens on one URL field", () => {
		const w = mountWizard();
		expect(w.find('[data-test="endpoint-url"]').exists()).toBe(true);
		expect(w.find('[data-test="preflight-steps"]').exists()).toBe(false);
	});

	it("refuses a non-https URL without calling AR", async () => {
		const w = mountWizard();
		await check(w, "http://acme.example/mcp");
		expect(beginConnect).not.toHaveBeenCalled();
		expect(w.find('[data-test="error"]').text()).toMatch(/https/i);
	});

	it("renders the preflight rows AR returned", async () => {
		beginConnect.mockResolvedValue({
			handle: "h-1",
			preflight: PREFLIGHT_OAUTH,
			authorize_url: "https://auth.acme.example/authorize?x=1",
			redirect_uri: "https://ar.example.com/cb",
		});
		const w = mountWizard();
		await check(w);
		expect(w.findAll('[data-test="preflight-step"]')).toHaveLength(2);
	});

	it("stops at the failure and shows its next action", async () => {
		beginConnect.mockResolvedValue({
			handle: "h-1",
			preflight: {
				...PREFLIGHT_OAUTH,
				steps: [
					{
						key: "reachable",
						label: "Reachable",
						status: "fail",
						detail: "No DNS record.",
						next_action: "Check the hostname.",
					},
				],
			},
		});
		const w = mountWizard();
		await check(w);
		expect(w.find('[data-test="auth-step"]').exists()).toBe(false);
		expect(w.find('[data-test="error"]').text()).toContain("Check the hostname.");
	});

	it("moves to needs-auth when the server wants OAuth", async () => {
		beginConnect.mockResolvedValue({
			handle: "h-1",
			preflight: PREFLIGHT_OAUTH,
			authorize_url: "https://auth.acme.example/authorize?x=1",
			redirect_uri: "https://ar.example.com/cb",
		});
		const w = mountWizard();
		await check(w);
		expect(w.find('[data-test="auth-step"]').exists()).toBe(true);
		expect(w.find('[data-test="connect"]').text()).toContain("Acme Tasks");
	});

	it("skips straight to review when the server needs no auth", async () => {
		beginConnect.mockResolvedValue({
			handle: "h-1",
			preflight: { ...PREFLIGHT_OAUTH, auth: { scheme: "none", supports_dcr: false, scopes: [] } },
		});
		getConnectSession.mockResolvedValue({ status: "Authorized", capabilities: CAPS });
		const w = mountWizard();
		await check(w);
		expect(w.find('[data-test="capability-review"]').exists()).toBe(true);
	});
});

describe("ConnectWizard away and return", () => {
	beforeEach(() => {
		beginConnect.mockReset();
		getConnectSession.mockReset();
		commitConnect.mockReset().mockResolvedValue({ success: true });
		abandonConnect.mockReset().mockResolvedValue({ success: true });
		beginReauth.mockReset();
		// No browser storage to reset: reauth mode is read off the session
		// payload's reauth_server_name, so nothing about it survives in this tab.
		navigateTo.mockReset();
		vi.stubGlobal("location", {
			href: "https://fac.example/copilot/settings/connections",
			assign: navigateTo,
		});
	});

	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it("reconstructs at review from a ?connect= handle", async () => {
		// reauth_server_name is null on the ordinary add path — Part 3 returns the
		// key on every session response, not only on reconnects.
		getConnectSession.mockResolvedValue({
			status: "Authorized",
			endpoint_url: "https://acme.example/mcp",
			preflight: PREFLIGHT_OAUTH,
			capabilities: CAPS,
			reauth_server_name: null,
		});
		const w = mountWizard({ initialHandle: "h-1" });
		await flushPromises();
		expect(getConnectSession).toHaveBeenCalledWith("h-1");
		expect(w.find('[data-test="capability-review"]').exists()).toBe(true);
	});

	it("reconstructs at needs-auth when the round trip never finished", async () => {
		// Title Case WITH A SPACE — the doctype Select value verbatim, matching
		// AR User MCP Server.status. "AwaitingAuth" is not a status AR emits.
		getConnectSession.mockResolvedValue({
			status: "Awaiting Auth",
			endpoint_url: "https://acme.example/mcp",
			preflight: PREFLIGHT_OAUTH,
			authorize_url: "https://auth.acme.example/authorize?x=1",
			capabilities: null,
		});
		const w = mountWizard({ initialHandle: "h-1" });
		await flushPromises();
		expect(w.find('[data-test="auth-step"]').exists()).toBe(true);
	});

	it("a resumed session can still be sent on to the authorization server", async () => {
		// authorize_url is a real stored value on the session (Small Text, not
		// Data — a PKCE authorize URL with scopes and state blows past 140
		// chars). A user who reloaded mid-flow must be able to click Connect.
		getConnectSession.mockResolvedValue({
			status: "Awaiting Auth",
			endpoint_url: "https://acme.example/mcp",
			preflight: PREFLIGHT_OAUTH,
			authorize_url: "https://auth.acme.example/authorize?state=abc&scope=tasks.read",
			capabilities: null,
		});
		const w = mountWizard({ initialHandle: "h-1" });
		await flushPromises();
		await w.find('[data-test="connect"]').trigger("click");
		expect(w.find('[data-test="away"]').exists()).toBe(true);
		expect(w.find('[data-test="error"]').exists()).toBe(false);
	});

	it("still shows the Preflight status as a check in progress", async () => {
		getConnectSession.mockResolvedValue({
			status: "Preflight",
			endpoint_url: "https://acme.example/mcp",
			preflight: PREFLIGHT_OAUTH,
			capabilities: null,
		});
		const w = mountWizard({ initialHandle: "h-1" });
		await flushPromises();
		expect(w.find('[data-test="auth-step"]').exists()).toBe(true);
	});

	it("surfaces AR's own message when the session failed", async () => {
		getConnectSession.mockResolvedValue({
			status: "Failed",
			error_message: "The authorization server refused the exchange.",
			preflight: PREFLIGHT_OAUTH,
		});
		const w = mountWizard({ initialHandle: "h-1" });
		await flushPromises();
		expect(w.find('[data-test="error"]').text()).toContain("refused the exchange");
	});

	it("re-begins with manual credentials, abandoning the DCR-less session first", async () => {
		beginConnect.mockResolvedValue({
			handle: "h-1",
			preflight: { ...PREFLIGHT_OAUTH, auth: { ...PREFLIGHT_OAUTH.auth, supports_dcr: false } },
			redirect_uri: "https://ar.example.com/cb",
		});
		const w = mountWizard();
		await check(w);

		beginConnect.mockResolvedValue({
			handle: "h-2",
			preflight: { ...PREFLIGHT_OAUTH, auth: { ...PREFLIGHT_OAUTH.auth, supports_dcr: false } },
			authorize_url: "https://auth.acme.example/authorize?x=2",
			redirect_uri: "https://ar.example.com/cb",
		});
		await w.find('[data-test="client-id"]').setValue("cid-123");
		await w.find('[data-test="submit-credentials"]').trigger("click");
		await flushPromises();

		expect(abandonConnect).toHaveBeenCalledWith("h-1");
		expect(beginConnect).toHaveBeenLastCalledWith("https://acme.example/mcp", "cid-123", "");
	});
});

describe("ConnectWizard commit", () => {
	beforeEach(() => {
		beginConnect.mockReset();
		getConnectSession.mockReset();
		commitConnect.mockReset().mockResolvedValue({ success: true });
		abandonConnect.mockReset().mockResolvedValue({ success: true });
		beginReauth.mockReset();
		// No browser storage to reset: reauth mode is read off the session
		// payload's reauth_server_name, so nothing about it survives in this tab.
		navigateTo.mockReset();
		vi.stubGlobal("location", {
			href: "https://fac.example/copilot/settings/connections",
			assign: navigateTo,
		});
	});

	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it("commits the reviewed name and announces the addition", async () => {
		getConnectSession.mockResolvedValue({ status: "Authorized", preflight: PREFLIGHT_OAUTH, capabilities: CAPS });
		const w = mountWizard({ initialHandle: "h-1" });
		await flushPromises();
		await w.find('[data-test="add"]').trigger("click");
		await flushPromises();

		expect(commitConnect).toHaveBeenCalledWith("h-1", "Acme Tasks");
		expect(w.emitted("added")[0]).toEqual(["Acme Tasks"]);
		expect(w.find('[data-test="added"]').exists()).toBe(true);
	});

	it("re-authorization skips review and commits under the existing name", async () => {
		// reauth_server_name on the payload is what marks this a reconnect. The
		// prop agrees here; the next describe proves the payload wins when they
		// disagree, and that the payload alone is enough.
		getConnectSession.mockResolvedValue({
			status: "Authorized",
			preflight: PREFLIGHT_OAUTH,
			capabilities: CAPS,
			reauth_server_name: "Acme Tasks",
		});
		const w = mountWizard({ initialHandle: "h-1", reauthServerName: "Acme Tasks" });
		await flushPromises();

		expect(w.find('[data-test="capability-review"]').exists()).toBe(false);
		expect(commitConnect).toHaveBeenCalledWith("h-1", "Acme Tasks");
	});

	it("abandons an unfinished session when the user closes the wizard", async () => {
		beginConnect.mockResolvedValue({
			handle: "h-1",
			preflight: PREFLIGHT_OAUTH,
			authorize_url: "https://auth.acme.example/authorize?x=1",
			redirect_uri: "https://ar.example.com/cb",
		});
		const w = mountWizard();
		await check(w);
		await w.find('[data-test="close"]').trigger("click");
		expect(abandonConnect).toHaveBeenCalledWith("h-1");
		expect(w.emitted("close")).toHaveLength(1);
	});

	it("does not abandon a session it already committed", async () => {
		getConnectSession.mockResolvedValue({ status: "Authorized", preflight: PREFLIGHT_OAUTH, capabilities: CAPS });
		const w = mountWizard({ initialHandle: "h-1" });
		await flushPromises();
		await w.find('[data-test="add"]').trigger("click");
		await flushPromises();
		await w.find('[data-test="close"]').trigger("click");
		expect(abandonConnect).not.toHaveBeenCalled();
	});
});

describe("ConnectWizard reauthorization", () => {
	beforeEach(() => {
		beginConnect.mockReset();
		getConnectSession.mockReset();
		commitConnect.mockReset().mockResolvedValue({ success: true });
		abandonConnect.mockReset().mockResolvedValue({ success: true });
		beginReauth.mockReset();
		// No browser storage to reset: reauth mode is read off the session
		// payload's reauth_server_name, so nothing about it survives in this tab.
		navigateTo.mockReset();
		vi.stubGlobal("location", {
			href: "https://fac.example/copilot/settings/connections",
			assign: navigateTo,
		});
	});

	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it("opens a reconnect through beginReauth, never beginConnect", async () => {
		// beginConnect + commit-under-the-existing-name took the ADD path and
		// always hit the duplicate-name guard. beginReauth sets reauth_target,
		// which is what makes commit update the row in place.
		beginReauth.mockResolvedValue({
			handle: "h-9",
			preflight: PREFLIGHT_OAUTH,
			authorize_url: "https://auth.acme.example/authorize?x=9",
			redirect_uri: "https://ar.example.com/cb",
			reauth_server_name: "Acme Tasks",
		});
		const w = mountWizard({ reauthServerName: "Acme Tasks" });
		await flushPromises();

		expect(beginReauth).toHaveBeenCalledWith("Acme Tasks");
		expect(beginConnect).not.toHaveBeenCalled();
		// No URL field: AR reads the endpoint from the row being re-authorized,
		// so a reconnect cannot silently retarget a different server.
		expect(w.find('[data-test="endpoint-url"]').exists()).toBe(false);
		expect(w.find('[data-test="auth-step"]').exists()).toBe(true);
	});

	it("carries the reauth target across the round trip on the payload alone", async () => {
		beginReauth.mockResolvedValue({
			handle: "h-9",
			preflight: PREFLIGHT_OAUTH,
			authorize_url: "https://auth.acme.example/authorize?x=9",
			reauth_server_name: "Acme Tasks",
		});
		const first = mountWizard({ reauthServerName: "Acme Tasks" });
		await flushPromises();
		await first.find('[data-test="connect"]').trigger("click");
		expect(navigateTo).toHaveBeenCalledWith("https://auth.acme.example/authorize?x=9");

		// The browser left and came back on ?connect=h-9 with no prop telling the
		// wizard this was a reconnect. The session says so: AR set reauth_target,
		// and Part 3 returns it as reauth_server_name on every session response.
		getConnectSession.mockResolvedValue({
			status: "Authorized",
			endpoint_url: "https://acme.example/mcp",
			preflight: PREFLIGHT_OAUTH,
			capabilities: CAPS,
			reauth_server_name: "Acme Tasks",
		});
		const second = mountWizard({ initialHandle: "h-9" });
		await flushPromises();

		expect(second.find('[data-test="capability-review"]').exists()).toBe(false);
		expect(commitConnect).toHaveBeenCalledWith("h-9", "Acme Tasks");
	});

	it("resumes a reconnect in a fresh context and never trips the duplicate-name refusal", async () => {
		// The whole point of reading reauth mode off the payload: this mount has
		// NO prior browser state of any kind — a different tab, a different
		// device, a restarted browser, storage blocked. Only the deep link's
		// handle survived. existingNames deliberately contains the very name being
		// reconnected, so if the wizard fell through to CapabilityReview its
		// client-side duplicate check would refuse a name nobody is changing.
		getConnectSession.mockResolvedValue({
			status: "Authorized",
			endpoint_url: "https://acme.example/mcp",
			preflight: PREFLIGHT_OAUTH,
			capabilities: CAPS,
			reauth_server_name: "Acme Tasks",
		});
		const w = mountWizard({
			initialHandle: "h-9",
			existingNames: ["Acme Tasks", "Main Frappe Site"],
		});
		await flushPromises();

		expect(w.find('[data-test="capability-review"]').exists()).toBe(false);
		expect(w.find('[data-test="error"]').exists()).toBe(false);
		expect(commitConnect).toHaveBeenCalledWith("h-9", "Acme Tasks");
		expect(w.emitted("added")[0]).toEqual(["Acme Tasks"]);
	});

	it("lets the payload override the prop, in both directions", async () => {
		// The prop is a starting hint from ConnectionCard; the payload is what AR
		// actually recorded on the session. Where they disagree the payload wins.
		getConnectSession.mockResolvedValue({
			status: "Authorized",
			endpoint_url: "https://acme.example/mcp",
			preflight: PREFLIGHT_OAUTH,
			capabilities: CAPS,
			reauth_server_name: "Acme Tasks Renamed",
		});
		const reconnect = mountWizard({ initialHandle: "h-9", reauthServerName: "Stale Hint" });
		await flushPromises();
		expect(commitConnect).toHaveBeenCalledWith("h-9", "Acme Tasks Renamed");

		commitConnect.mockClear();

		// A null reauth_server_name is authoritative too: it says this session is
		// an ordinary add, so the wizard reviews rather than committing silently.
		getConnectSession.mockResolvedValue({
			status: "Authorized",
			endpoint_url: "https://acme.example/mcp",
			preflight: PREFLIGHT_OAUTH,
			capabilities: CAPS,
			reauth_server_name: null,
		});
		const add = mountWizard({ initialHandle: "h-8", reauthServerName: "Stale Hint" });
		await flushPromises();
		expect(add.find('[data-test="capability-review"]').exists()).toBe(true);
		expect(commitConnect).not.toHaveBeenCalled();
	});
});
