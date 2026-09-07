// Billing form validation.
//
// Mirrors the server rules in assistant_runtime_payments
// `api/billing_details._validate_billing_input`, so a customer sees a bad
// field before a round trip. The server stays authoritative — it holds India
// Compliance's tables and applies the pincode-to-state range check this file
// deliberately leaves to it.
//
// STATE_NUMBERS is India Compliance's own table (gst_india/constants), minus
// "Other Countries" (96), which is not an Indian state. It must stay in step:
// a state the server does not know is rejected on save, which is how
// "Lakshadweep" — IC calls it "Lakshadweep Islands" — silently made that
// territory unable to save its billing details at all.
export const STATE_NUMBERS = {
	"Andaman and Nicobar Islands": "35",
	"Andhra Pradesh": "37",
	"Arunachal Pradesh": "12",
	"Assam": "18",
	"Bihar": "10",
	"Chandigarh": "04",
	"Chhattisgarh": "22",
	"Dadra and Nagar Haveli and Daman and Diu": "26",
	"Delhi": "07",
	"Goa": "30",
	"Gujarat": "24",
	"Haryana": "06",
	"Himachal Pradesh": "02",
	"Jammu and Kashmir": "01",
	"Jharkhand": "20",
	"Karnataka": "29",
	"Kerala": "32",
	"Ladakh": "38",
	"Lakshadweep Islands": "31",
	"Madhya Pradesh": "23",
	"Maharashtra": "27",
	"Manipur": "14",
	"Meghalaya": "17",
	"Mizoram": "15",
	"Nagaland": "13",
	"Odisha": "21",
	"Other Territory": "97",
	"Puducherry": "34",
	"Punjab": "03",
	"Rajasthan": "08",
	"Sikkim": "11",
	"Tamil Nadu": "33",
	"Telangana": "36",
	"Tripura": "16",
	"Uttar Pradesh": "09",
	"Uttarakhand": "05",
	"West Bengal": "19",
};

export const INDIAN_STATES = Object.keys(STATE_NUMBERS);

export const COUNTRIES = [
	{ code: "IN", label: "India" },
	{ code: "US", label: "United States" },
	{ code: "GB", label: "United Kingdom" },
	{ code: "AU", label: "Australia" },
	{ code: "CA", label: "Canada" },
	{ code: "DE", label: "Germany" },
	{ code: "FR", label: "France" },
	{ code: "JP", label: "Japan" },
	{ code: "SG", label: "Singapore" },
];

// Shape only — the check digit is verified server-side by India Compliance.
const GSTIN_SHAPE = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][A-Z0-9]Z[A-Z0-9]$/;
// Six digits, no leading zero (India Compliance's PINCODE_FORMAT).
const PINCODE_SHAPE = /^[1-9][0-9]{5}$/;
// Deliberately permissive: 8-15 digits covers E.164 and every country we sell
// in. A leading + is optional on input and normalised on save.
const PHONE_SHAPE = /^\+?[0-9][0-9\s\-().]{7,20}$/;
const EMAIL_SHAPE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const blank = (value) => !String(value ?? "").trim();

/**
 * Validate the billing form.
 *
 * @param {object} form
 * @returns {Record<string, string>} field name -> message, empty when valid.
 *   Keys match the server's field names so a server-side rejection can be
 *   attached to the same input.
 */
export function validateBillingForm(form = {}) {
	const errors = {};

	if (blank(form.billing_legal_name)) {
		errors.billing_legal_name =
			"Enter your registered business or legal name — it appears on your invoices.";
	}

	if (blank(form.billing_email)) {
		errors.billing_email = "Enter a billing email address.";
	} else if (!EMAIL_SHAPE.test(String(form.billing_email).trim())) {
		errors.billing_email = "Enter a valid billing email address.";
	}

	if (blank(form.billing_phone)) {
		errors.billing_phone = "Enter a phone number, including the country code.";
	} else if (!PHONE_SHAPE.test(String(form.billing_phone).trim())) {
		errors.billing_phone =
			"Enter a valid phone number with country code, e.g. +91 99 0000 0000.";
	}

	if (blank(form.billing_country)) {
		errors.billing_country = "Select your billing country.";
	}

	if (blank(form.billing_address_line1)) {
		errors.billing_address_line1 = "Enter the first line of your billing address.";
	}

	if (blank(form.billing_city)) {
		errors.billing_city = "Enter your city or town.";
	}

	if (form.billing_country !== "IN") return errors;

	const state = String(form.billing_state ?? "").trim();
	if (!state) {
		errors.billing_state =
			"Select your state — it decides how GST is split on your invoice.";
	} else if (!STATE_NUMBERS[state]) {
		errors.billing_state = "Select a valid Indian state from the list.";
	}

	const gstin = String(form.gstin ?? "").trim().toUpperCase();
	if (gstin) {
		if (!GSTIN_SHAPE.test(gstin)) {
			errors.gstin = "GSTIN must be 15 characters in the format ##AAAAA####A#Z#.";
		} else if (STATE_NUMBERS[state] && gstin.slice(0, 2) !== STATE_NUMBERS[state]) {
			// A GSTIN encodes its own state in the first two digits, so a
			// disagreement means one of the two is wrong — and either way the
			// invoice would carry the wrong place of supply.
			errors.gstin = `This GSTIN belongs to state code ${gstin.slice(0, 2)}, but you selected ${state} (${STATE_NUMBERS[state]}). Check the GSTIN or the state.`;
		}
	}

	const pincode = String(form.billing_pincode ?? "").trim();
	if (pincode && !PINCODE_SHAPE.test(pincode)) {
		errors.billing_pincode = "Enter a 6-digit postal code. It cannot start with 0.";
	}

	return errors;
}

/** Strip punctuation, keep a leading +, so the gateway receives E.164. */
export function normalisePhone(value) {
	const digits = String(value ?? "").trim().replace(/[^\d+]/g, "");
	if (!digits) return "";
	return digits.startsWith("+") ? digits : `+${digits}`;
}
