import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// One set of cases for both copies of the script approval: the ES module for the chat SPA, and
// the plain script the fac-pages Desk page inlines through render_include, which cannot load one.
const USER = "avery@example.com";
const NAME = "sales-a1b2c3";
// SHA-256("abc"), the FIPS 180-2 test vector.
const ABC_SHA256 = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";

export const personalPage = (extra = {}) => ({
	title: "Sales",
	html: "<p>Sales</p>",
	script: "root_element.querySelector('p').textContent = 'ran';",
	style: "",
	draft: false,
	visibility: "Only me",
	owner_is_me: true,
	...extra,
});

export function describePageApproval(label, api) {
	describe(`${label}: script approval`, () => {
		beforeEach(() => window.localStorage.clear());
		afterEach(() => {
			vi.restoreAllMocks();
			vi.unstubAllGlobals();
		});

		it("stores the approval per user and page, under the key Desk and the chat share", async () => {
			expect(api.fac_page_approval_key(USER, NAME)).toBe(`fac_page_approved:${USER}:${NAME}`);
			expect(await api.fac_page_approve_script(USER, NAME, "abc")).toBe(true);
			const stored = JSON.parse(window.localStorage.getItem(`fac_page_approved:${USER}:${NAME}`));
			expect(stored).toEqual({ hash: ABC_SHA256, script: "abc" });
			expect(api.fac_page_approved_script(USER, NAME)).toEqual(stored);
			expect(api.fac_page_approved_script("other@example.com", NAME)).toBeNull();
		});

		it("hashes with SHA-256, and with FNV-1a where the browser has no crypto.subtle", async () => {
			expect(await api.fac_page_script_hash("abc")).toBe(ABC_SHA256);
			vi.stubGlobal("crypto", {});
			expect(await api.fac_page_script_hash("abc")).toBe("fnv1a:1a47e90b");
		});

		it("asks on first open, saying there is no approved script yet", async () => {
			expect(await api.fac_page_script_review(USER, NAME, personalPage())).toEqual({ state: "first", approved: "" });
		});

		it("lets the approved script run, and asks again once FACO changes it", async () => {
			const page = personalPage();
			await api.fac_page_approve_script(USER, NAME, page.script);
			expect(await api.fac_page_script_review(USER, NAME, page)).toBeNull();
			expect(await api.fac_page_script_review(USER, NAME, { ...page, html: "<p>New</p>" })).toBeNull();
			const changed = { ...page, script: `${page.script}\nconsole.log(1);` };
			expect(await api.fac_page_script_review(USER, NAME, changed)).toEqual({
				state: "changed",
				approved: page.script,
			});
		});

		it("does not trust a stored hash that does not match the stored script", async () => {
			const page = personalPage();
			// Only a hand-edited or corrupted entry gets here; approval always stores the pair.
			const record = { hash: await api.fac_page_script_hash(page.script), script: "other" };
			window.localStorage.setItem(api.fac_page_approval_key(USER, NAME), JSON.stringify(record));
			expect((await api.fac_page_script_review(USER, NAME, page)).state).toBe("changed");
		});

		it("asks every time when storage throws", async () => {
			// A private window or blocked site data makes localStorage throw on every access.
			vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
				throw new Error("denied");
			});
			vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
				throw new Error("denied");
			});
			const page = personalPage();
			expect(await api.fac_page_approve_script(USER, NAME, page.script)).toBe(false);
			expect(api.fac_page_approved_script(USER, NAME)).toBeNull();
			expect((await api.fac_page_script_review(USER, NAME, page)).state).toBe("first");
		});

		it("never holds a shared page, someone else's page, a draft or a page without a script", async () => {
			for (const page of [
				personalPage({ visibility: "Shared" }),
				personalPage({ owner_is_me: false }),
				personalPage({ draft: true }),
				personalPage({ script: "  \n" }),
			]) {
				expect(api.fac_page_needs_review(page)).toBe(false);
				expect(await api.fac_page_script_review(USER, NAME, page)).toBeNull();
			}
			expect(api.fac_page_needs_review(personalPage())).toBe(true);
		});

		it("diffs the approved script against the new one, line by line", () => {
			expect(api.fac_page_line_diff("a\nb\nc", "a\nB\nc\nd")).toEqual([
				{ type: "same", text: "a" },
				{ type: "removed", text: "b" },
				{ type: "added", text: "B" },
				{ type: "same", text: "c" },
				{ type: "added", text: "d" },
			]);
			expect(api.fac_page_line_diff("", "x\ny")).toEqual([
				{ type: "added", text: "x" },
				{ type: "added", text: "y" },
			]);
		});
	});
}
