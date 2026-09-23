import { describe, it, expect } from "vitest";
import { parseRichBlocks } from "./parser";

const render = (md) => md;

function componentProps(content) {
	const parts = parseRichBlocks(content, render);
	return parts.filter((p) => p.type === "component").map((p) => p.props);
}

function htmlParts(content) {
	return parseRichBlocks(content, render)
		.filter((p) => p.type === "html")
		.map((p) => p.html);
}

// Live-bug repro: `metric` was the only rich block whose data lives entirely
// in fence-line attributes, while its sibling `chart` takes a JSON body. The
// model generalised from `chart` and emitted a JSON body for `metric` too —
// 11 of the 15 metric fences in real chat history use that shape. parseBody
// read only the attrs, so every one of them mounted MetricBlock with blank
// props and rendered as an empty bordered box with no error anywhere.
describe("metric fence dialects", () => {
	it("parses the documented fence-attribute form", () => {
		expect(
			componentProps('```metric title="Monthly Revenue" value="₹14,25,000" change="+18%" trend="up"\n```')
		).toEqual([
			{
				title: "Monthly Revenue",
				value: "₹14,25,000",
				change: "+18%",
				trend: "up",
				description: "",
			},
		]);
	});

	it("parses a JSON body using label/value — the shape the model actually emits", () => {
		expect(
			componentProps('```metric\n{"label":"Companies shortlisted","value":"15"}\n```')
		).toEqual([
			{
				title: "Companies shortlisted",
				value: "15",
				change: "",
				trend: "",
				description: "",
			},
		]);
	});

	it("maps a JSON suffix onto the description line", () => {
		expect(
			componentProps('```metric\n{"label": "Hotel / Lodging", "value": "USD 275", "suffix": "/ night"}\n```')
		).toEqual([
			{
				title: "Hotel / Lodging",
				value: "USD 275",
				change: "",
				trend: "",
				description: "/ night",
			},
		]);
	});

	it("coerces non-string JSON values so a numeric value still renders", () => {
		expect(componentProps('```metric\n{"label":"Open tickets","value":15}\n```')).toEqual([
			{ title: "Open tickets", value: "15", change: "", trend: "", description: "" },
		]);
	});

	it("ignores presentational JSON keys it has no slot for", () => {
		// `color` and `status` show up in real output; neither maps onto a
		// MetricBlock prop and `status: "success"` is explicitly NOT a trend
		// direction, so they are dropped rather than guessed at.
		expect(
			componentProps('```metric\n{"label":"Priority","value":"High","status":"success","color":"blue"}\n```')
		).toEqual([{ title: "Priority", value: "High", change: "", trend: "", description: "" }]);
	});

	it("lets fence attributes win when a fence mixes both dialects", () => {
		expect(
			componentProps('```metric title="From attrs" value="1"\n{"label":"From body","value":"2"}\n```')
		).toEqual([
			{ title: "From attrs", value: "1", change: "", trend: "", description: "" },
		]);
	});

	it("handles a message that mixes both dialects across fences", () => {
		// MSG-2026-06645 did exactly this: the attr cards rendered, the JSON
		// cards came out blank in the same reply.
		const props = componentProps(
			'```metric title="May 2026 Total" value="₹2,57,668" trend="flat"\n```\n\n' +
				'```metric\n{"label": "June 2026 Total", "value": "₹4,25,394", "color": "green"}\n```'
		);
		expect(props.map((p) => [p.title, p.value])).toEqual([
			["May 2026 Total", "₹2,57,668"],
			["June 2026 Total", "₹4,25,394"],
		]);
	});

	it("falls back to a visible code block when a metric carries nothing renderable", () => {
		// The silent-empty-box failure mode is the actual defect. Anything we
		// can't turn into a card must stay visible so it's reportable.
		const content = '```metric\n{"headline":"unknown shape"}\n```';
		expect(componentProps(content)).toEqual([]);
		expect(htmlParts(content)[0]).toContain("unknown shape");
	});

	it("falls back to a code block for an entirely empty metric fence", () => {
		expect(componentProps("```metric\n```")).toEqual([]);
	});
});

describe("other rich block dialects still parse", () => {
	it("keeps chart JSON-body parsing intact", () => {
		expect(
			componentProps('```chart\n{"type":"bar","data":{"categories":["x"],"series":[]}}\n```')
		).toEqual([{ config: { type: "bar", data: { categories: ["x"], series: [] } } }]);
	});

	it("renders a malformed chart as a code block rather than a component", () => {
		expect(componentProps("```chart\nnot json\n```")).toEqual([]);
	});

	it("keeps callout attribute + body parsing intact", () => {
		expect(componentProps('```callout type="warning" title="Heads up"\nBody text\n```')).toEqual([
			{ type: "warning", title: "Heads up", body: "Body text" },
		]);
	});
});

// Live-bug repro (client instance, 2026-08-24): the same "generalised from
// `chart`" mistake, two shapes further on. Both reached a real user's screen
// as visible JSON.
describe("callout fence with a JSON body", () => {
	it("reads type, title and content out of a JSON body", () => {
		expect(
			componentProps(
				'```callout\n{"type":"warning","title":"Data quality caveat","content":"All 216 Leads were bulk-imported."}\n```'
			)
		).toEqual([
			{
				type: "warning",
				title: "Data quality caveat",
				body: "All 216 Leads were bulk-imported.",
			},
		]);
	});

	it("lets fence attributes win over the JSON body", () => {
		expect(
			componentProps(
				'```callout type="error" title="From attrs"\n{"type":"warning","title":"From body","content":"Text"}\n```'
			)
		).toEqual([{ type: "error", title: "From attrs", body: "Text" }]);
	});

	it("accepts body/text/message as aliases for content", () => {
		expect(
			componentProps('```callout\n{"type":"tip","message":"Try the filter."}\n```')
		).toEqual([{ type: "tip", title: "", body: "Try the filter." }]);
	});

	it("leaves a plain markdown body untouched", () => {
		expect(
			componentProps('```callout type="info" title="Note"\nPlain **markdown** body.\n```')
		).toEqual([{ type: "info", title: "Note", body: "Plain **markdown** body." }]);
	});

	it("keeps an unrecognised JSON body visible rather than silently blank", () => {
		const props = componentProps('```callout\n{"headline":"unknown shape"}\n```');
		expect(props).toHaveLength(1);
		expect(props[0].body).toContain("headline");
	});
});

describe("metric fence carrying a JSON array", () => {
	it("renders one card per array entry", () => {
		expect(
			componentProps(
				'```metric\n[{"label":"Communications logged (all time)","value":"16"},' +
					'{"label":"Logged against a Lead/Opp/Customer","value":"9"}]\n```'
			)
		).toEqual([
			{
				title: "Communications logged (all time)",
				value: "16",
				change: "",
				trend: "",
				description: "",
			},
			{
				title: "Logged against a Lead/Opp/Customer",
				value: "9",
				change: "",
				trend: "",
				description: "",
			},
		]);
	});

	it("skips entries with neither a title nor a value", () => {
		expect(
			componentProps('```metric\n[{"label":"Kept","value":"1"},{"note":"dropped"}]\n```')
		).toEqual([
			{ title: "Kept", value: "1", change: "", trend: "", description: "" },
		]);
	});

	it("falls back to a code block when no entry is usable", () => {
		const content = '```metric\n[{"note":"a"},{"note":"b"}]\n```';
		expect(componentProps(content)).toEqual([]);
		expect(htmlParts(content).join("")).toContain("note");
	});
});
