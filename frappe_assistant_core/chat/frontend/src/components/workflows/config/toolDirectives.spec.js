import { describe, it, expect } from "vitest";
import {
	bareToolName,
	healToolName,
	makeDirective,
	normalizeDirectives,
	serverForDirective,
	deriveMCPServers,
	resolutionIndex,
	toolDiscoveryState,
	serversNeedingReconnect,
} from "@/components/workflows/config/toolDirectives";

// The shape AR's api/tools.py:list_tools actually returns.
const LIST_DOCUMENTS = {
	name: "Main Frappe Site:list_documents",
	original_name: "list_documents",
	server: "Main Frappe Site",
	description: "List documents of a doctype",
};

describe("makeDirective", () => {
	it("writes the bare tool name the engine resolves against", () => {
		const directive = makeDirective(LIST_DOCUMENTS);
		expect(directive.tool_name).toBe("list_documents");
		expect(directive.capability).toBe("list_documents");
	});

	it("never writes the server-prefixed name", () => {
		expect(makeDirective(LIST_DOCUMENTS).tool_name).not.toContain(":");
	});

	it("does not write input_guidance", () => {
		expect(makeDirective(LIST_DOCUMENTS)).not.toHaveProperty("input_guidance");
	});

	it("falls back to name when a tool carries no original_name", () => {
		expect(bareToolName({ name: "web_search" })).toBe("web_search");
		expect(makeDirective({ name: "web_search" }).tool_name).toBe("web_search");
	});
});

describe("healToolName", () => {
	it("strips a server prefix saved by an older builder", () => {
		expect(healToolName("Main Frappe Site:list_documents")).toBe("list_documents");
	});

	it("leaves a bare name alone", () => {
		expect(healToolName("list_documents")).toBe("list_documents");
	});

	it("keeps everything after the first colon", () => {
		expect(healToolName("srv:ns:tool")).toBe("ns:tool");
	});
});

describe("normalizeDirectives", () => {
	it("heals prefixed names and reports the change", () => {
		const { directives, changed } = normalizeDirectives([
			{ tool_name: "Main Frappe Site:list_documents", capability: "list_documents" },
		]);
		expect(directives[0].tool_name).toBe("list_documents");
		expect(changed).toBe(true);
	});

	it("drops input_guidance", () => {
		const { directives, changed } = normalizeDirectives([
			{ tool_name: "list_documents", input_guidance: {} },
		]);
		expect(directives[0]).not.toHaveProperty("input_guidance");
		expect(changed).toBe(true);
	});

	it("reports no change for an already-clean directive", () => {
		const { changed } = normalizeDirectives([
			{ tool_name: "list_documents", capability: "list_documents", required: true },
		]);
		expect(changed).toBe(false);
	});
});

describe("deriveMCPServers", () => {
	it("derives the server of each configured tool", () => {
		const servers = deriveMCPServers(
			[makeDirective(LIST_DOCUMENTS)],
			[LIST_DOCUMENTS],
			[]
		);
		expect(servers).toEqual(["Main Frappe Site"]);
	});

	it("skips (returns null) when the tool inventory failed to load", () => {
		expect(deriveMCPServers([{ tool_name: "list_documents" }], [], [])).toBeNull();
	});

	it("keeps servers already configured when the inventory is unavailable", () => {
		// A directive whose prefix still names its server is derivable offline.
		const servers = deriveMCPServers(
			[{ tool_name: "Brave:web_search" }],
			[],
			["Main Frappe Site"]
		);
		expect(servers).toEqual(expect.arrayContaining(["Main Frappe Site", "Brave"]));
	});

	it("is additive — removing a tool never narrows to an empty list", () => {
		const servers = deriveMCPServers([], [LIST_DOCUMENTS], ["Main Frappe Site"]);
		expect(servers).toEqual(["Main Frappe Site"]);
	});
});

describe("serverForDirective", () => {
	it("matches on the bare name", () => {
		expect(serverForDirective({ tool_name: "list_documents" }, [LIST_DOCUMENTS])).toBe(
			"Main Frappe Site"
		);
	});

	it("falls back to the prefix when the tool is not in the inventory", () => {
		expect(serverForDirective({ tool_name: "Brave:web_search" }, [])).toBe("Brave");
	});

	it("returns an empty string when nothing is knowable", () => {
		expect(serverForDirective({ tool_name: "web_search" }, [])).toBe("");
	});
});

describe("resolutionIndex", () => {
	it("indexes by the healed directive name", () => {
		const index = resolutionIndex([
			{ tool_name: "Main Frappe Site:list_documents", status: "resolved" },
		]);
		expect(index.get("list_documents").status).toBe("resolved");
	});
});

describe("toolDiscoveryState", () => {
	it("reports ok when tools came back", () => {
		expect(toolDiscoveryState({ result: { success: true, tools: [LIST_DOCUMENTS] } })).toBe(
			"ok"
		);
	});

	it("reports failed when the passthrough itself failed", () => {
		expect(toolDiscoveryState({ result: { success: false, tools: [] } })).toBe("failed");
	});

	it("reports auth when a server reported an expired token", () => {
		const result = {
			success: true,
			tools: [],
			errors: [{ server: "Main Frappe Site", error_code: "REFRESH_TOKEN_EXPIRED" }],
		};
		expect(toolDiscoveryState({ result })).toBe("auth");
		expect(serversNeedingReconnect(result)).toEqual(["Main Frappe Site"]);
	});

	it("distinguishes no-servers from a server that genuinely has no tools", () => {
		expect(
			toolDiscoveryState({ result: { success: true, tools: [], servers_queried: [] } })
		).toBe("no-servers");
		expect(
			toolDiscoveryState({
				result: { success: true, tools: [], servers_queried: ["Main Frappe Site"] },
			})
		).toBe("empty");
	});

	it("reports loading while the call is in flight", () => {
		expect(toolDiscoveryState({ result: null, isLoading: true })).toBe("loading");
	});
});
