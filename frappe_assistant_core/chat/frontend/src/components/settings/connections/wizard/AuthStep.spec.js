import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import AuthStep from "./AuthStep.vue";

const SERVER_INFO = { name: "Acme Tasks", version: "2.1.0", protocol_version: "2025-06-18" };

const DCR_AUTH = {
	scheme: "oauth",
	authorization_server: "https://auth.acme.example",
	supports_dcr: true,
	scopes: ["tasks.read", "tasks.write"],
	issuer: "https://auth.acme.example",
};

const MANUAL_AUTH = { ...DCR_AUTH, supports_dcr: false };

const AUTHORIZE_URL = "https://auth.acme.example/authorize?client_id=cid-123&state=abc";

const mountStep = (auth, extra = {}) =>
	mount(AuthStep, {
		props: {
			serverInfo: SERVER_INFO,
			auth,
			redirectUri: "https://ar.example.com/api/method/assistant_runtime.api.mcp_oauth.callback",
			...extra,
		},
	});

// A DCR begin returns an authorize_url in the same payload, so these mounts
// carry one. Omitting it is what let a non-DCR server with a hand-registered
// client fall through to the credentials form forever.
const mountDcr = (extra = {}) => mountStep(DCR_AUTH, { authorizeUrl: AUTHORIZE_URL, ...extra });

describe("AuthStep with DCR", () => {
	it("names the server it found, from initialize", () => {
		const w = mountDcr();
		expect(w.find('[data-test="auth-server-name"]').text()).toContain("Acme Tasks");
	});

	it("names the authorization server and the scopes it wants", () => {
		const w = mountDcr();
		expect(w.find('[data-test="auth-server"]').text()).toContain("https://auth.acme.example");
		expect(w.find('[data-test="auth-scopes"]').text()).toContain("tasks.read");
		expect(w.find('[data-test="auth-scopes"]').text()).toContain("tasks.write");
	});

	it("offers exactly one connect button, labelled with the server", async () => {
		const w = mountDcr();
		const button = w.find('[data-test="connect"]');
		expect(button.text()).toBe("Connect to Acme Tasks");
		await button.trigger("click");
		expect(w.emitted("connect")).toHaveLength(1);
	});

	it("hides the manual escape hatch entirely", () => {
		const w = mountDcr();
		expect(w.find('[data-test="manual-panel"]').exists()).toBe(false);
	});
});

describe("AuthStep without DCR", () => {
	it("shows the redirect URI the user has to register", () => {
		const w = mountStep(MANUAL_AUTH);
		expect(w.find('[data-test="redirect-uri"]').text()).toContain(
			"assistant_runtime.api.mcp_oauth.callback"
		);
	});

	it("refuses to submit without a client ID", async () => {
		const w = mountStep(MANUAL_AUTH);
		await w.find('[data-test="submit-credentials"]').trigger("click");
		expect(w.emitted("credentials")).toBeUndefined();
		expect(w.find('[data-test="auth-error"]').text()).toMatch(/client ID/i);
	});

	it("emits the credentials it was given, trimmed", async () => {
		const w = mountStep(MANUAL_AUTH);
		await w.find('[data-test="client-id"]').setValue("  cid-123  ");
		await w.find('[data-test="client-secret"]').setValue("shh");
		await w.find('[data-test="submit-credentials"]').trigger("click");
		expect(w.emitted("credentials")[0][0]).toEqual({
			client_id: "cid-123",
			client_secret: "shh",
		});
	});

	it("shows no one-click connect button", () => {
		const w = mountStep(MANUAL_AUTH);
		expect(w.find('[data-test="connect"]').exists()).toBe(false);
	});
});

describe("AuthStep fallbacks", () => {
	it("survives a server that gave no name", () => {
		const w = mount(AuthStep, {
			props: {
				serverInfo: { name: null },
				auth: DCR_AUTH,
				redirectUri: "https://x/cb",
				authorizeUrl: AUTHORIZE_URL,
			},
		});
		expect(w.find('[data-test="connect"]').text()).toBe("Connect to this server");
	});

	it("says so when no scopes were advertised", () => {
		const w = mountStep({ ...DCR_AUTH, scopes: [] });
		expect(w.find('[data-test="auth-scopes"]').text()).toMatch(/none requested/i);
	});

	it("disables the connect button while the container is busy", () => {
		const w = mountDcr({ busy: true });
		expect(w.find('[data-test="connect"]').attributes("disabled")).toBeDefined();
	});
});

describe("AuthStep once a sign-in link exists", () => {
	// The bug: this branch keyed off `auth.supports_dcr`, which is a fixed fact
	// about the server (`bool(registration_endpoint)`). A server without DCR
	// could never show the sign-in button, so after the user pasted a client and
	// AR built a real authorize_url, the wizard re-rendered the same form and
	// looked like nothing had happened.
	it("offers the sign-in button for a server that has no DCR", async () => {
		const w = mountStep(MANUAL_AUTH, { authorizeUrl: AUTHORIZE_URL });

		const button = w.find('[data-test="connect"]');
		expect(button.exists()).toBe(true);
		await button.trigger("click");
		expect(w.emitted("connect")).toHaveLength(1);
	});

	it("stops asking for credentials it already has", () => {
		const w = mountStep(MANUAL_AUTH, { authorizeUrl: AUTHORIZE_URL });
		expect(w.find('[data-test="manual-panel"]').exists()).toBe(false);
	});

	it("still asks for credentials when there is no link yet", () => {
		const w = mountStep(MANUAL_AUTH);
		expect(w.find('[data-test="manual-panel"]').exists()).toBe(true);
		expect(w.find('[data-test="connect"]').exists()).toBe(false);
	});

	it("lets a DCR server whose registration failed be rescued by hand", () => {
		// supports_dcr is true — the server advertises a registration endpoint —
		// but AR came back without a link, so registration did not produce one.
		// Offering the form beats a button that can only report its own failure.
		const w = mountStep(DCR_AUTH);
		expect(w.find('[data-test="manual-panel"]').exists()).toBe(true);
		expect(w.find('[data-test="connect"]').exists()).toBe(false);
	});
});
