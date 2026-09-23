import { describe, it, expect, beforeAll } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import vm from "node:vm";

/**
 * The desk widget carries its own port of the SPA's rich-block renderer, and
 * the two drift: the JSON-body tolerance `metric` gained in the SPA was never
 * ported here, so the widget ignored the body outright and rendered an empty
 * card — worse than the SPA, which at least fell back to a visible code block.
 *
 * Executed rather than pattern-matched: these are rendering rules, and a
 * regex over the source cannot tell an empty card from a populated one.
 */
const widgetJs = resolve(process.cwd(), "../../public/chat/widget/widget_richblocks.js");

let RichBlocks;

beforeAll(() => {
	const sandbox = {
		window: {},
		// The widget's markdown pass. Identity is enough — these tests are
		// about which text reaches it, not how it is formatted.
		FACOCore: { format_message: (text) => String(text) },
	};
	sandbox.globalThis = sandbox;
	vm.createContext(sandbox);
	new vm.Script(readFileSync(widgetJs, "utf8")).runInContext(sandbox);
	RichBlocks = sandbox.window.FACOWidgetRichBlocks;
});

const process_ = (content) => RichBlocks.process(content);

describe("widget callout fence", () => {
	it("renders the documented fence-attribute form", () => {
		const html = process_('```callout type="warning" title="Heads up"\nBody text\n```');
		expect(html).toContain("faco-rb-callout-warning");
		expect(html).toContain("Heads up");
		expect(html).toContain("Body text");
	});

	it("reads type, title and content out of a JSON body", () => {
		const html = process_(
			'```callout\n{"type":"warning","title":"Data quality caveat","content":"All 216 Leads were bulk-imported."}\n```'
		);
		expect(html).toContain("faco-rb-callout-warning");
		expect(html).toContain("Data quality caveat");
		expect(html).toContain("All 216 Leads were bulk-imported.");
		// The whole point: the raw JSON must not reach the user.
		expect(html).not.toContain('"type":"warning"');
	});

	it("lets fence attributes win over the JSON body", () => {
		const html = process_(
			'```callout type="error" title="From attrs"\n{"type":"warning","title":"From body","content":"Text"}\n```'
		);
		expect(html).toContain("faco-rb-callout-error");
		expect(html).toContain("From attrs");
		expect(html).not.toContain("From body");
	});
});

describe("widget metric fence", () => {
	it("renders the documented fence-attribute form", () => {
		const html = process_(
			'```metric title="Monthly Revenue" value="Rs 14,25,000" change="+18%" trend="up"\n```'
		);
		expect(html).toContain("Monthly Revenue");
		expect(html).toContain("Rs 14,25,000");
		expect(html).toContain("+18%");
	});

	it("reads a JSON object body keyed on label/value", () => {
		const html = process_('```metric\n{"label":"Companies shortlisted","value":"15"}\n```');
		expect(html).toContain("faco-rb-metric");
		expect(html).toContain("Companies shortlisted");
		expect(html).toContain("15");
		expect(html).not.toContain('"label"');
	});

	it("maps a JSON suffix onto the description line", () => {
		const html = process_(
			'```metric\n{"label":"Hotel / Lodging","value":"USD 275","suffix":"/ night"}\n```'
		);
		expect(html).toContain("faco-rb-metric-desc");
		expect(html).toContain("/ night");
	});

	it("renders one card per entry of a JSON array", () => {
		const html = process_(
			'```metric\n[{"label":"Communications logged (all time)","value":"16"},' +
				'{"label":"Logged against a Lead/Opp/Customer","value":"9"}]\n```'
		);
		expect(html.match(/faco-rb-metric"/g) || []).toHaveLength(2);
		expect(html).toContain("Communications logged (all time)");
		expect(html).toContain("Logged against a Lead/Opp/Customer");
		expect(html).not.toContain('"label"');
	});

	it("coerces a numeric JSON value rather than dropping it", () => {
		const html = process_('```metric\n{"label":"Open tickets","value":15}\n```');
		expect(html).toContain("Open tickets");
		expect(html).toContain("15");
	});

	it("escapes markup coming out of a JSON body", () => {
		const html = process_('```metric\n{"label":"<script>x</script>","value":"1"}\n```');
		expect(html).not.toContain("<script>");
		expect(html).toContain("&lt;script&gt;");
	});

	it("falls back to a visible code block when the fence yields nothing", () => {
		const html = process_('```metric\n{"headline":"unknown shape"}\n```');
		expect(html).not.toContain("faco-rb-metric");
		expect(html).toContain("headline");
	});
});
