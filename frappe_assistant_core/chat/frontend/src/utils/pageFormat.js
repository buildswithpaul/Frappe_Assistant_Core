/**
 * `frappe.format` for a page script outside Desk: the text Desk's own `frappe.format` shows.
 *
 * Desk's formatter returns html (`<div style='text-align: right'>₹ 79,360.00</div>`); a page in Desk
 * gets its text content (fac_page_frappe.js), and so does a page here. The functions below are
 * ports of Frappe's frappe/public/js/frappe/form/formatters.js, utils/number_format.js,
 * utils/datatype.js and the date part of utils/datetime.js, line for line where the result
 * depends on it. They read the site's settings from `settings` (get_page's `format_settings`)
 * where Desk reads `frappe.boot.sysdefaults` and the `:Currency` docs it boots with.
 * pageFormat.parity.spec.js checks them against Frappe's own code.
 */

/**
 * @typedef {object} FormatSettings
 * @property {string} [number_format] e.g. "#,##,###.##"
 * @property {string} [currency] the site's default currency
 * @property {string} [currency_precision] "" when the currency's number format decides
 * @property {string} [float_precision]
 * @property {string} [date_format] e.g. "dd-mm-yyyy"
 * @property {string} [time_format] e.g. "HH:mm:ss"
 * @property {string} [hide_currency_symbol] "Yes" or "1" hides it
 * @property {string} [rounding_method]
 * @property {string} [use_number_format_from_currency] "1" to use each currency's own format
 * @property {Object<string, {symbol?: string, symbol_on_right?: number, number_format?: string, fraction_units?: number}>} [currencies]
 *   the enabled currencies
 */

// frappe.number_format_info
const NUMBER_FORMAT_INFO = {
	"#,###.##": { decimal_str: ".", group_sep: "," },
	"#.###,##": { decimal_str: ",", group_sep: "." },
	"# ###.##": { decimal_str: ".", group_sep: " " },
	"# ###,##": { decimal_str: ",", group_sep: " " },
	"#'###.##": { decimal_str: ".", group_sep: "'" },
	"#, ###.##": { decimal_str: ".", group_sep: ", " },
	"#,##,###.##": { decimal_str: ".", group_sep: "," },
	"#,###.###": { decimal_str: ".", group_sep: "," },
	"#.###": { decimal_str: "", group_sep: "." },
	"#,###": { decimal_str: "", group_sep: "," },
};

const cstr = (s) => (s == null ? "" : s + "");

function lstrip(s, chars) {
	while (chars.includes(s.substr(0, 1))) s = s.substr(1);
	return s;
}

function cint(v, def) {
	if (v === true) return 1;
	if (v === false) return 0;
	v = v + "";
	if (v !== "0") v = lstrip(v, ["0"]);
	v = parseInt(v);
	if (isNaN(v)) v = def === undefined ? 0 : def;
	return v;
}

const isNull = (v) => v === null || v === undefined || cstr(v).trim() === "";

const currencyDoc = (settings, currency) => (settings.currencies || {})[currency] || {};

function getNumberFormat(settings, currency) {
	return (
		(cint(settings.use_number_format_from_currency) === 1 &&
			currency &&
			currencyDoc(settings, currency).number_format) ||
		settings.number_format ||
		"#,###.##"
	);
}

function getNumberFormatInfo(settings, format) {
	if (!format) format = getNumberFormat(settings);
	const info = { ...(NUMBER_FORMAT_INFO[format] || { decimal_str: ".", group_sep: "," }) };
	info.precision = info.decimal_str == "" ? 0 : format.split(info.decimal_str).slice(1)[0].length;
	return info;
}

function stripNumberGroups(settings, v, numberFormat) {
	if (!numberFormat) numberFormat = getNumberFormat(settings);
	const info = getNumberFormatInfo(settings, numberFormat);
	v = v.replace(new RegExp(info.group_sep === "." ? "\\." : info.group_sep, "g"), "");
	if (info.decimal_str !== "." && info.decimal_str !== "") {
		v = v.replace(new RegExp(info.decimal_str, "g"), ".");
	}
	return v;
}

function round(settings, num, precision) {
	const method = settings.rounding_method || "Banker's Rounding (legacy)";
	const isNegative = num < 0;

	if (method == "Banker's Rounding (legacy)") {
		const d = cint(precision);
		const m = Math.pow(10, d);
		const n = +(d ? Math.abs(num) * m : Math.abs(num)).toFixed(8);
		const i = Math.floor(n);
		const f = n - i;
		let r = !precision && f == 0.5 ? (i % 2 == 0 ? i : i + 1) : Math.round(n);
		r = d ? r / m : r;
		return isNegative ? -r : r;
	}
	if (method == "Banker's Rounding") {
		if (num == 0) return 0.0;
		precision = cint(precision);
		const multiplier = Math.pow(10, precision);
		num = Math.abs(num) * multiplier;
		const floorNum = Math.floor(num);
		const decimalPart = num - floorNum;
		const epsilon = 2.0 ** (Math.log2(Math.abs(num)) - 52.0);
		const isTie = epsilon < 0.5 ? Math.abs(decimalPart - 0.5) < epsilon : decimalPart == 0.5;
		num = isTie ? (floorNum % 2 == 0 ? floorNum : floorNum + 1) : Math.round(num);
		num = num / multiplier;
		return isNegative ? -num : num;
	}
	if (method == "Commercial Rounding") {
		if (num == 0) return 0.0;
		const multiplier = Math.pow(10, cint(precision));
		num = num * multiplier;
		let epsilon = 2.0 ** (Math.log2(Math.abs(num)) - 52.0);
		if (epsilon >= 0.25) epsilon = 0;
		num = Math.sign(num) * Math.round(Math.abs(num) + epsilon);
		return num / multiplier;
	}
	// Desk throws here; a page shows its figures unrounded rather than not at all.
	return num;
}

function flt(settings, v, decimals, numberFormat) {
	if (v == null || v == "") return 0;
	if (typeof v !== "number") {
		v = v + "";
		// strip a currency symbol; a space could also be a group separator
		if (v.indexOf(" ") != -1) {
			const parts = v.split(" ");
			v = isNaN(parseFloat(parts[0])) ? parts.slice(parts.length - 1).join(" ") : v;
		}
		v = parseFloat(stripNumberGroups(settings, v, numberFormat));
		if (isNaN(v)) v = 0;
	}
	if (decimals != null) return round(settings, v, decimals);
	return v;
}

/** Desk's window.format_number. */
export function formatNumber(settings, v, format, decimals) {
	if (!format) {
		format = getNumberFormat(settings);
		if (decimals == null) decimals = cint(settings.float_precision) || 3;
	}
	const info = getNumberFormatInfo(settings, format);
	if (decimals == null) decimals = info.precision;

	v = flt(settings, v, decimals, format);
	const isNegative = v < 0;
	v = Math.abs(v).toFixed(decimals);

	const part = v.split(".");
	let groupPosition = info.group_sep ? 3 : 0;
	if (groupPosition) {
		const integer = part[0];
		let str = "";
		for (let i = integer.length; i >= 0; i--) {
			let l = str.split(info.group_sep).join("").length;
			if (format == "#,##,###.##" && str.indexOf(",") != -1) {
				// Indian grouping: 2 digits after the first group of 3
				groupPosition = 2;
				l += 1;
			}
			str += integer.charAt(i);
			if (l && !((l + 1) % groupPosition) && i != 0) str += info.group_sep;
		}
		part[0] = str.split("").reverse().join("");
	}
	if (part[0] + "" == "") part[0] = "0";
	part[1] = part[1] && info.decimal_str ? info.decimal_str + part[1] : "";
	return (isNegative ? "-" : "") + part[0] + part[1];
}

function currencySymbol(settings, currency) {
	if (["1", "Yes"].includes(settings.hide_currency_symbol)) return null;
	if (!currency) currency = settings.currency;
	return currencyDoc(settings, currency).symbol || currency;
}

/** Desk's format_currency. Desk translates the symbol with __; no site translates one. */
export function formatCurrency(settings, v, currency, decimals) {
	const format = getNumberFormat(settings, currency);
	const symbol = currencySymbol(settings, currency);
	if (decimals === undefined) decimals = settings.currency_precision || null;
	if (symbol) {
		return currencyDoc(settings, currency).symbol_on_right
			? formatNumber(settings, v, format, decimals) + " " + symbol
			: symbol + " " + formatNumber(settings, v, format, decimals);
	}
	return formatNumber(settings, v, format, decimals);
}

// frappe.meta.get_field_currency. Desk also falls back to the open form (cur_frm), and reads a
// "Company:company:default_currency" option from records it has loaded; a page has neither.
function fieldCurrency(settings, df, doc) {
	let currency = settings.currency || "USD";
	if (df && df.options && df.options.indexOf(":") == -1 && doc && doc[df.options]) {
		currency = doc[df.options];
	}
	return currency;
}

// frappe.meta.get_field_precision
function fieldPrecision(settings, df, doc) {
	if (df && df.precision) return cint(df.precision);
	if (df && df.fieldtype === "Currency") {
		const currencyPrecision = settings.currency_precision;
		if (currencyPrecision !== null && currencyPrecision !== undefined && currencyPrecision !== "") {
			return cint(currencyPrecision);
		}
		return getNumberFormatInfo(settings, getNumberFormat(settings, fieldCurrency(settings, df, doc))).precision;
	}
	return cint(settings.float_precision) || 3;
}

const DATE = /^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{1,2})(?::(\d{1,2}))?)?/;
const pad = (n, width = 2) => String(n).padStart(width, "0");

function dateParts(value) {
	if (value instanceof Date) {
		if (Number.isNaN(value.getTime())) return null;
		return {
			year: value.getFullYear(),
			month: value.getMonth() + 1,
			day: value.getDate(),
			hour: value.getHours(),
			minute: value.getMinutes(),
			second: value.getSeconds(),
		};
	}
	const match = DATE.exec(String(value));
	if (!match) return null;
	const [year, month, day, hour, minute, second] = match.slice(1).map((n) => Number(n || 0));
	const valid = new Date(year, month - 1, day);
	if (valid.getMonth() !== month - 1 || valid.getDate() !== day) return null;
	return { year, month, day, hour, minute, second };
}

// The tokens of Frappe's date_format and time_format choices, as moment formats them.
const TOKENS = /YYYY|YY|MM|DD|HH|mm|ss/g;

function render(parts, momentFormat) {
	return momentFormat.replace(TOKENS, (token) => {
		switch (token) {
			case "YYYY":
				return pad(parts.year, 4);
			case "YY":
				return pad(parts.year % 100);
			case "MM":
				return pad(parts.month);
			case "DD":
				return pad(parts.day);
			case "HH":
				return pad(parts.hour);
			case "mm":
				return pad(parts.minute);
			default:
				return pad(parts.second);
		}
	});
}

/**
 * Desk's frappe.datetime.str_to_user: a date in the site's date format, and a datetime with the
 * site's time format after it. Desk also moves a datetime into the user's time zone; this
 * leaves it in the site's, which is the same unless the user set their own.
 */
export function strToUser(settings, value, onlyDate = false) {
	if (!value) return "";
	const parts = dateParts(value);
	if (!parts) return "Invalid date";
	const dateFormat = (settings.date_format || "yyyy-mm-dd").toUpperCase();
	if (onlyDate || (typeof value === "string" && value.indexOf(" ") === -1)) return render(parts, dateFormat);
	return render(parts, `${dateFormat} ${settings.time_format || "HH:mm:ss"}`);
}

// Each returns what Desk's formatter of that fieldtype returns, less its html wrapper.
const FORMATTERS = {
	Data(settings, value) {
		return value == null ? "" : value;
	},
	Float(settings, value, df, options, doc) {
		if (value === null) return "";
		let precision = df.precision || cint(settings.float_precision) || null;
		if (df.options && df.options.trim()) {
			// options names a currency field, at the precision of a float
			return FORMATTERS.Currency(settings, value, { ...df, precision }, options, doc);
		}
		// 1.000000 shows as 1
		if (!(options || {}).always_show_decimals && !isNull(value) && flt(settings, value) % 1 === 0) {
			precision = 0;
		}
		value = value == null || value === "" ? "" : value;
		return formatNumber(settings, value, null, precision);
	},
	Int(settings, value) {
		if (value === null) return "";
		return value == null ? "" : cint(value);
	},
	Percent(settings, value, df) {
		if (value === null) return "";
		const [mantissa, exponent] = cstr(value).toLowerCase().split("e");
		const valuePrecision = Math.max((mantissa.split(".")[1]?.length || 0) - cint(exponent), 0);
		const precision = df.precision || cint(settings.float_precision) || 2;
		return formatNumber(settings, value, null, Math.min(precision, valuePrecision)) + "%";
	},
	Currency(settings, value, df, options, doc) {
		if (value === null) return "";
		const currency = fieldCurrency(settings, df, doc);
		let precision =
			typeof df.precision == "number" || df.precision ? cint(df.precision) : fieldPrecision(settings, df, doc);

		// A value with fewer decimals than the precision shows as many as its currency has.
		if (precision > 2) {
			const parts = cstr(value).split(".");
			const decimals = parts.length > 1 ? parts[1] : "";
			if (decimals.length < 3 || decimals.length < precision) {
				const fraction = currencyDoc(settings, currency).fraction_units || 100;
				if (decimals.length < cstr(fraction).length) precision = cstr(fraction).length - 1;
			}
		}
		value = value == null || value === "" ? "" : value;
		return formatCurrency(settings, value, currency, precision);
	},
	Date(settings, value) {
		if (value) {
			value = strToUser(settings, value, true);
			if (value === "Invalid date") value = null;
		}
		return value || "";
	},
};

/**
 * The text content of formatted html, parsed in a detached document that is never shown: no
 * script in it runs and nothing in it loads. Desk's page frappe does the same (fac_page_frappe.js).
 */
export function htmlText(html) {
	if (html == null) return "";
	return new DOMParser().parseFromString(String(html), "text/html").body.textContent;
}

/**
 * The text Desk's frappe.format(value, df, options, doc) shows, for Currency, Float, Int, Percent,
 * Date, and any other fieldtype as Data. As in Desk, a Currency's `options` names the field of
 * `doc` that holds its currency, such as "currency", not a currency code.
 *
 * @param {FormatSettings} settings
 */
export function formatValue(settings, value, df, options, doc) {
	if (!df) df = { fieldtype: "Data" };
	const fieldtype = String(df.fieldtype || "Data").replace(/ /g, "");
	const formatter = FORMATTERS[fieldtype] || FORMATTERS.Data;
	return htmlText(formatter(settings || {}, value, df, options, doc));
}
