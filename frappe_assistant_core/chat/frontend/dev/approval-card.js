// Dev-only harness: mounts the real ApprovalCard with fixed blocks, one section per check of
// the batch approval card (#34411). See approval-card.html for how to start it.
import { createApp, h, ref } from "vue";
import "@/styles/fonts.css";
import "@/styles/quiet-ledger.css";
import ApprovalCard from "@/components/chat/interactions/ApprovalCard.vue";

const interrupts = [{ id: "i1", reason: { type: "approval" } }];
const lines = (n) => Array.from({ length: n }, (_, i) => `line_${i + 1} = frappe.db.get_value("Item", "ITEM-${i + 1}", "item_name")`).join("\n");
// 500 characters whose end can be checked: the last characters are "END-OF-500".
const description500 = `${"Long description for the approval card. ".repeat(13)}`.slice(0, 490) + "END-OF-500";

function range(count, make) {
	return Array.from({ length: count }, (_, i) => make(i + 1));
}

const fixtures = [
	{
		id: "records-100",
		title: "1. 100 records: 40 Customer Groups, 30 Territories, 30 UOMs",
		block: {
			tool_name: "create_document",
			input: {
				documents: [
					...range(40, (n) => ({
						doctype: "Customer Group",
						data: { customer_group_name: `Group ${n}`, parent_customer_group: "All Customer Groups" },
					})),
					...range(30, (n) => ({
						doctype: "Territory",
						data: { territory_name: `Zone ${n}`, parent_territory: "All Territories" },
					})),
					...range(30, (n) => ({
						doctype: "UOM",
						data: n % 2 ? { uom_name: `Unit ${n}`, must_be_whole_number: 1 } : { uom_name: `Unit ${n}` },
					})),
				],
			},
		},
	},
	{
		id: "hidden-keys",
		title: "2. Hidden keys: _assign and __newname",
		block: {
			tool_name: "create_document",
			input: {
				documents: [
					{
						doctype: "Customer Group",
						data: {
							customer_group_name: "Retail",
							parent_customer_group: "All Customer Groups",
							_assign: '["a@x.com"]',
							__newname: "Retail-01",
						},
					},
					{ doctype: "Customer Group", data: { customer_group_name: "Wholesale", parent_customer_group: "All Customer Groups" } },
				],
			},
		},
	},
	{
		id: "long-value",
		title: "3. Long value: a 500-character description and a 60-line script",
		block: {
			tool_name: "create_document",
			input: {
				documents: [
					{ doctype: "Web Page", data: { title: "Help", description: description500, script: lines(60) } },
					{ doctype: "Web Page", data: { title: "About", description: "Short" } },
				],
			},
		},
	},
	{
		id: "child-rows",
		title: "4. Child rows: an update with 3 rows, one with _delete",
		block: {
			tool_name: "update_document",
			input: {
				documents: [
					{
						doctype: "Note",
						name: "NOTE-0001",
						data: {
							seen_by: [
								{ name: "row-1", user: "a@x.com" },
								{ name: "row-2", user: "b@x.com", _delete: true },
								{ user: "c@x.com" },
							],
						},
					},
					{ doctype: "Note", name: "NOTE-0002", data: { public: 1 } },
				],
			},
		},
	},
	{
		id: "single-record",
		title: "5. Single record: a ToDo with a long description",
		block: {
			tool_name: "create_document",
			input: {
				doctype: "ToDo",
				data: {
					description: description500,
					priority: "High",
					date: "2026-11-02",
					allocated_to: "a@x.com",
					role: "Accounts User",
					reference_type: "Customer",
				},
			},
		},
	},
];

const Harness = {
	setup() {
		const events = ref([]);
		const log = (kind) => (id, responses) => events.value.unshift(`${kind} ${id} ${JSON.stringify(responses)}`);
		return () =>
			h("main", { class: "harness" }, [
				h("h1", "Approval card harness (dev only)"),
				...fixtures.map((fixture) =>
					h("section", { id: fixture.id, "data-fixture": fixture.id }, [
						h("h2", fixture.title),
						h(ApprovalCard, {
							block: { id: fixture.id, interrupts, ...fixture.block },
							onApprove: log("approve"),
							onReject: log("reject"),
						}),
					]),
				),
				h("section", { id: "events" }, [h("h2", "Events"), h("pre", { "data-test": "events" }, events.value.join("\n"))]),
			]);
	},
};

const style = document.createElement("style");
style.textContent = `
body { margin: 0; background: var(--ql-bg, #fbfaf8); color: var(--ql-text, #222); font-family: system-ui, sans-serif; }
.harness { max-width: 720px; margin: 0 auto; padding: 16px; }
.harness h1 { font-size: 18px; }
.harness h2 { font-size: 13px; margin: 28px 0 6px; color: var(--ql-text-secondary, #555); }
.harness pre { font-size: 11px; white-space: pre-wrap; }
`;
document.head.appendChild(style);

createApp(Harness).mount("#app");
