import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

const SRC = resolve(process.cwd(), "src");
const BILLING_DIR = join(SRC, "components/settings/billing");
const billingSettings = () => readFileSync(join(SRC, "components/settings/BillingSettings.vue"), "utf8");

// Specs are excluded deliberately: a component named in a test is not a
// component the app renders, and counting those would let this guard pass on
// its own prose.
function walk(dir) {
	return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
		const full = join(dir, entry.name);
		if (entry.isDirectory()) {
			return ["node_modules", "__tests__"].includes(entry.name) ? [] : walk(full);
		}
		if (/\.spec\.js$/.test(entry.name)) return [];
		return /\.(vue|js)$/.test(entry.name) ? [full] : [];
	});
}

/**
 * The billing Overview shipped unmounted: `OverviewTab` came across in the
 * FACO→FAC merge carrying the usage chart and the expiring-credit warning, and
 * nothing ever rendered it. Both components kept being restyled, and the
 * backend rollup built to feed the chart kept being maintained, while the page
 * itself silently lost the feature. These guard the wiring, not the markup.
 */
describe("BillingSettings wiring", () => {
	it("warns about expiring credits on the billing page", () => {
		expect(billingSettings()).toMatch(/<ExpiringCreditsBanner/);
	});

	it("renders the usage chart in the Credits tab", () => {
		const creditsPanel = billingSettings().match(
			/<UsageChart[\s\S]{0,200}?\/>|<UsageChart[^>]*>/
		);
		expect(creditsPanel).not.toBeNull();
		expect(billingSettings()).toMatch(/activeTab === 'credits'[\s\S]*?<UsageChart/);
	});

	it("leaves no billing component orphaned", () => {
		const sources = walk(SRC).filter((f) => statSync(f).isFile());
		const orphans = readdirSync(BILLING_DIR)
			.filter((f) => f.endsWith(".vue"))
			.filter((f) => {
				const base = f.replace(/\.vue$/, "");
				const own = join(BILLING_DIR, f);
				return !sources.some(
					(s) => s !== own && new RegExp(`\\b${base}\\b`).test(readFileSync(s, "utf8"))
				);
			});
		expect(orphans).toEqual([]);
	});
});
