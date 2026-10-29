// The values pageFormat.parity.spec.js formats both ways: with Frappe's own formatter and with
// the chat's (pageFormat.js). pageFormatCases.desk.json holds what Frappe's gave for each.

export const NUMBER_FORMATS = ["#,##,###.##", "#,###.##", "#.###,##", "# ###.##", "#'###.##", "#,###.###", "#,###"];

const CURRENCIES = {
	INR: { symbol: "₹", symbol_on_right: 0, number_format: "#,##,###.##", fraction_units: 100 },
	USD: { symbol: "$", symbol_on_right: 0, number_format: "#,###.##", fraction_units: 100 },
	EUR: { symbol: "€", symbol_on_right: 1, number_format: "#.###,##", fraction_units: 100 },
	KWD: { symbol: "KD", symbol_on_right: 0, number_format: "#,###.###", fraction_units: 1000 },
	CHF: { symbol: "Fr", symbol_on_right: 0, number_format: "#'###.##", fraction_units: 100 },
};

/** A site's format_settings, as get_page serves them (api/fac_page.py page_format_settings). */
export function site(overrides = {}) {
	return {
		number_format: "#,##,###.##",
		currency: "INR",
		currency_precision: "",
		float_precision: "3",
		date_format: "dd-mm-yyyy",
		time_format: "HH:mm:ss",
		hide_currency_symbol: "",
		rounding_method: "Banker's Rounding",
		use_number_format_from_currency: "0",
		currencies: CURRENCIES,
		...overrides,
	};
}

const VALUES = [-1234567.891, -0.5, 0, 0.005, 1.005, 2.5, 3.5, 7, 1234.5, 79360, 123456789.126, 9999999.995];
const NUMERIC = ["Currency", "Float", "Int", "Percent"];

const cases = [];
const add = (title, settings, value, df, options, doc) => cases.push({ title, settings, value, df, options, doc });

for (const format of NUMBER_FORMATS) {
	const settings = site({ number_format: format });
	for (const fieldtype of NUMERIC) {
		for (const value of VALUES) add(`${fieldtype} ${value} in ${format}`, settings, value, { fieldtype });
	}
	// A value read from the page's html rather than a record arrives as text.
	add(`Currency "1234.56" in ${format}`, settings, "1234.56", { fieldtype: "Currency" });
	add(`Float "1,234.5" in ${format}`, settings, "1,234.5", { fieldtype: "Float" });
}

for (const currency of ["INR", "USD", "EUR", "KWD", "CHF", "JPY"]) {
	add(`Currency in the record's ${currency}`, site(), 1234567.5, { fieldtype: "Currency", options: "currency" }, null, {
		currency,
	});
}
add("Currency with a currency code as options", site(), 1234.5, { fieldtype: "Currency", options: "USD" });
add("Currency with a three-part options", site(), 1234.5, { fieldtype: "Currency", options: "Company:company:default_currency" }, null, {
	company: "Acme",
});
add("Currency with each currency's own format", site({ use_number_format_from_currency: "1" }), 1234567.5, {
	fieldtype: "Currency",
	options: "currency",
}, null, { currency: "EUR" });
add("Currency with the symbol hidden", site({ hide_currency_symbol: "Yes" }), 79360, { fieldtype: "Currency" });
add("Currency with the symbol hidden by 1", site({ hide_currency_symbol: "1" }), 79360, { fieldtype: "Currency" });
add("Currency with the symbol shown by No", site({ hide_currency_symbol: "No" }), 79360, { fieldtype: "Currency" });
for (const value of [1.5, 1.555, "1.5", 2]) {
	add(`Currency ${JSON.stringify(value)} at currency precision 3`, site({ currency_precision: "3" }), value, {
		fieldtype: "Currency",
	});
	add(`Currency ${JSON.stringify(value)} in KWD at currency precision 3`, site({ currency_precision: "3" }), value, {
		fieldtype: "Currency",
		options: "currency",
	}, null, { currency: "KWD" });
}
add("Currency at currency precision 0", site({ currency_precision: "0" }), 1234.56, { fieldtype: "Currency" });
add("Currency with the field's precision", site(), 1234.56789, { fieldtype: "Currency", precision: 4 });
add("Currency with no site currency", site({ currency: null }), 1234.5, { fieldtype: "Currency" });
add("Currency null", site(), null, { fieldtype: "Currency" });
add("Currency empty", site(), "", { fieldtype: "Currency" });
add("Float naming a currency field", site(), 1234.5, { fieldtype: "Float", options: "currency" }, null, { currency: "USD" });
add("Float with the field's precision", site(), 1234.5, { fieldtype: "Float", precision: 1 });
add("Float always showing decimals", site(), 7, { fieldtype: "Float" }, { always_show_decimals: 1 });
add("Float with no site precision", site({ float_precision: "" }), 1234.56789, { fieldtype: "Float" });
add("Percent with no site precision", site({ float_precision: "" }), 12.3456, { fieldtype: "Percent" });
add("Percent with the field's precision", site(), 12.3456, { fieldtype: "Percent", precision: 1 });
add("Percent of a small float", site(), 1e-7, { fieldtype: "Percent" });
add("Int of text", site(), "042", { fieldtype: "Int" });
add("Int null", site(), null, { fieldtype: "Int" });
for (const method of ["Banker's Rounding (legacy)", "Banker's Rounding", "Commercial Rounding"]) {
	for (const value of [0.125, 2.675, 1.005, -2.5, 0.5]) {
		add(`Currency ${value} by ${method}`, site({ rounding_method: method }), value, { fieldtype: "Currency" });
		add(`Int-like Float ${value} by ${method}`, site({ rounding_method: method }), value, { fieldtype: "Float", precision: 0 });
	}
}
for (const dateFormat of ["dd-mm-yyyy", "dd/mm/yyyy", "dd.mm.yyyy", "mm/dd/yyyy", "mm-dd-yyyy", "yyyy-mm-dd"]) {
	const settings = site({ date_format: dateFormat });
	add(`Date in ${dateFormat}`, settings, "2026-10-29", { fieldtype: "Date" });
	add(`Date of a datetime in ${dateFormat}`, settings, "2026-03-07 13:05:09", { fieldtype: "Date" });
}
add("Date that does not exist", site(), "2026-02-30", { fieldtype: "Date" });
add("Date empty", site(), "", { fieldtype: "Date" });
add("Date with no site format", site({ date_format: null }), "2026-10-29", { fieldtype: "Date" });
add("Data with an ampersand", site(), "A & B Traders", { fieldtype: "Data" });
add("Data with markup", site(), "<b>Bold</b> & co", { fieldtype: "Data" });
add("Data number", site(), 42, { fieldtype: "Data" });
add("Data null", site(), null, { fieldtype: "Data" });
add("no df", site(), "plain", undefined);
add("Small Text", site(), "two words", { fieldtype: "Small Text" });

// The rows the pages-in-chat skill example reads, as frappe.db.get_list returns them, and its
// call for each: facPageFrappe.spec.js runs the example in Desk and in the chat panel.
export const EXAMPLE_SITE = site();
export const EXAMPLE_ROWS = [
	{ name: "ACC-SINV-0001", customer: "A & B Traders", outstanding_amount: 79360, party_account_currency: "INR" },
	{ name: "ACC-SINV-0002", customer: "Globex <Ltd>", outstanding_amount: 1234567.5, party_account_currency: "USD" },
	{ name: "ACC-SINV-0003", customer: "Zürich AG", outstanding_amount: 0.5, party_account_currency: "CHF" },
];
export const EXAMPLE_DF = { fieldtype: "Currency", options: "party_account_currency" };
export const exampleTitle = (row) => `skill example: ${row.name}`;
for (const row of EXAMPLE_ROWS) add(exampleTitle(row), EXAMPLE_SITE, row.outstanding_amount, EXAMPLE_DF, null, row);

/** Each case: {title, settings, value, df, options, doc}. Titles are unique; they key the fixture. */
export const FORMAT_CASES = cases;
