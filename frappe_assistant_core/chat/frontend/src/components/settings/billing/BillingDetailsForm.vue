<template>
	<div class="billing-details">
		<div class="details-header">
			<h3 class="details-title">Billing Details</h3>
			<p class="details-description">
				GSTIN, address, and country are written to your ERPNext Customer record and drive
				how tax is split on every invoice.
			</p>
		</div>

		<div v-if="gateMessage" class="gate-banner">
			<svg
				class="gate-icon"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
				/>
			</svg>
			<span>{{ gateMessage }}</span>
		</div>

		<div v-if="loading" class="skeleton">Loading…</div>

		<form v-else @submit.prevent="save" class="details-form" novalidate>
			<BillingField
				for-id="bd-legal-name"
				label="Business / Legal Name"
				label-hint="as registered"
				required
				:error="errorFor('billing_legal_name')"
			>
				<input
					id="bd-legal-name"
					v-model.trim="form.billing_legal_name"
					type="text"
					class="form-input"
					:class="{ 'input-error': errorFor('billing_legal_name') }"
					placeholder="Acme Technologies Pvt Ltd"
					@blur="validateField('billing_legal_name')"
					@input="clearFieldError('billing_legal_name')"
				/>
				<template #hint>
					This is the name your invoices are issued to. For GST-registered
					businesses it must match the name on your GSTIN.
				</template>
			</BillingField>

			<BillingField
				for-id="bd-email"
				label="Billing Email"
				required
				:error="errorFor('billing_email')"
			>
				<input
					id="bd-email"
					v-model="form.billing_email"
					type="email"
					class="form-input"
					:class="{ 'input-error': errorFor('billing_email') }"
					placeholder="billing@example.com"
					@blur="validateField('billing_email')"
					@input="clearFieldError('billing_email')"
				/>
			</BillingField>

			<BillingField
				for-id="bd-phone"
				label="Billing Phone"
				label-hint="include country code"
				required
				:error="errorFor('billing_phone')"
			>
				<input
					id="bd-phone"
					v-model="form.billing_phone"
					type="tel"
					class="form-input"
					:class="{ 'input-error': errorFor('billing_phone') }"
					placeholder="+91 99 0000 0000"
					@blur="validateField('billing_phone')"
					@input="clearFieldError('billing_phone')"
				/>
				<template #hint>
					Razorpay requires a phone number to authorize recurring debits under
					India's NACH eMandate.
				</template>
			</BillingField>

			<BillingField
				for-id="bd-country"
				label="Country"
				required
				:error="errorFor('billing_country')"
			>
				<select
					id="bd-country"
					v-model="form.billing_country"
					class="form-input"
					:class="{ 'input-error': errorFor('billing_country') }"
					@change="clearFieldError('billing_country')"
				>
					<option v-for="c in COUNTRIES" :key="c.code" :value="c.code">
						{{ c.label }}
					</option>
				</select>
			</BillingField>

			<BillingGstFields
				v-if="form.billing_country === 'IN'"
				:form="form"
				:errors="fieldErrors"
				@update="(field, value) => (form[field] = value)"
				@validate="validateField"
				@clear="clearFieldError"
			/>

			<BillingField
				for-id="bd-line1"
				label="Address Line 1"
				required
				:error="errorFor('billing_address_line1')"
			>
				<input
					id="bd-line1"
					v-model="form.billing_address_line1"
					type="text"
					class="form-input"
					:class="{ 'input-error': errorFor('billing_address_line1') }"
					@blur="validateField('billing_address_line1')"
					@input="clearFieldError('billing_address_line1')"
				/>
			</BillingField>

			<BillingField for-id="bd-line2" label="Address Line 2">
				<input
					id="bd-line2"
					v-model="form.billing_address_line2"
					type="text"
					class="form-input"
				/>
			</BillingField>

			<div class="form-row">
				<BillingField
					for-id="bd-city"
					label="City"
					required
					:error="errorFor('billing_city')"
				>
					<input
						id="bd-city"
						v-model="form.billing_city"
						type="text"
						class="form-input"
						:class="{ 'input-error': errorFor('billing_city') }"
						@blur="validateField('billing_city')"
						@input="clearFieldError('billing_city')"
					/>
				</BillingField>
				<BillingField
					for-id="bd-pincode"
					label="Postal Code"
					:error="errorFor('billing_pincode')"
				>
					<input
						id="bd-pincode"
						v-model="form.billing_pincode"
						type="text"
						class="form-input"
						:class="{ 'input-error': errorFor('billing_pincode') }"
						@blur="validateField('billing_pincode')"
						@input="clearFieldError('billing_pincode')"
					/>
				</BillingField>
			</div>

			<p v-if="taxPreview" class="tax-preview">{{ taxPreview }}</p>

			<div v-if="saveError" class="field-error" role="alert">{{ saveError }}</div>
			<div v-if="saveSuccess" class="save-success">Billing details saved.</div>

			<button type="submit" class="save-btn" :disabled="saving">
				{{ saving ? "Saving…" : "Save" }}
			</button>
		</form>
	</div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, watch } from "vue";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";
import BillingField from "./BillingField.vue";
import BillingGstFields from "./BillingGstFields.vue";
import {
	COUNTRIES,
	INDIAN_STATES,
	normalisePhone,
	validateBillingForm,
} from "@/composables/_billing/billingValidation";

const props = defineProps({
	// Shown as a yellow banner above the form when non-empty (e.g. when
	// BillingSettings redirected the user here from a gated checkout).
	gateMessage: { type: String, default: "" },
});

const emit = defineEmits(["saved"]);

const loading = ref(true);
const saving = ref(false);
const saveError = ref("");
const saveSuccess = ref(false);
// One map keyed by the SAME field names the server uses, so a server-side
// rejection (which names its field — see billing_details._reject) lands on the
// same input as a client-side one.
const fieldErrors = ref({});
// Server field name -> input id, so a rejection can focus the input it names.
const FIELD_IDS = {
	billing_legal_name: "bd-legal-name",
	billing_email: "bd-email",
	billing_phone: "bd-phone",
	billing_country: "bd-country",
	gstin: "bd-gstin",
	billing_state: "bd-state",
	billing_address_line1: "bd-line1",
	billing_city: "bd-city",
	billing_pincode: "bd-pincode",
};
const errorFor = (field) => fieldErrors.value[field] || "";

const form = ref({
	billing_legal_name: "",
	billing_email: "",
	billing_phone: "",
	billing_country: "IN",
	gstin: "",
	billing_state: "",
	billing_city: "",
	billing_pincode: "",
	billing_address_line1: "",
	billing_address_line2: "",
});

const taxPreview = computed(() => {
	if (form.value.billing_country !== "IN") {
		return "Export of service — tax treatment depends on your LUT status.";
	}
	if (form.value.gstin) {
		return "B2B: Sales Invoice will issue with CGST+SGST (in-state) or IGST (inter-state) and your GSTIN for input tax credit.";
	}
	return "B2C: Sales Invoice will issue with CGST+SGST (in-state) or IGST (inter-state). Add a GSTIN to claim input credit.";
});

// Validation lives in `_billing/billingValidation` so it can be unit-tested
// and kept in step with the server's rules. Blur re-checks only the field the
// user just left, so typing in one input never lights up the whole form.
function validateField(field) {
	if (field === "billing_phone") {
		form.value.billing_phone = normalisePhone(form.value.billing_phone);
	}
	if (field === "gstin") {
		form.value.gstin = String(form.value.gstin || "").trim().toUpperCase();
	}
	const all = validateBillingForm(form.value);
	const next = { ...fieldErrors.value };
	if (all[field]) next[field] = all[field];
	else delete next[field];
	fieldErrors.value = next;
}

// Clear a field's error as soon as the user edits it — keeping a stale message
// under an input they are actively fixing reads as the form arguing with them.
function clearFieldError(field) {
	if (!fieldErrors.value[field]) return;
	const next = { ...fieldErrors.value };
	delete next[field];
	fieldErrors.value = next;
}

function focusField(field) {
	const el = document.getElementById(FIELD_IDS[field]);
	if (el) {
		el.focus();
		el.scrollIntoView({ block: "center", behavior: "smooth" });
	}
}

watch(
	() => form.value.billing_country,
	(c) => {
		// Clear India-only fields when switching to an overseas country.
		if (c !== "IN") {
			form.value.gstin = "";
			form.value.billing_state = "";
			clearFieldError("gstin");
			clearFieldError("billing_state");
		}
	}
);

async function load() {
	loading.value = true;
	try {
		const result = await api.billing.getBillingDetails();
		if (result) {
			Object.assign(form.value, result);
			// `billing_country` comes back as the ERPNext country name (e.g.
			// "India") — map it back to the ISO code the <select> expects.
			const match = COUNTRIES.find(
				(c) => c.label.toLowerCase() === String(form.value.billing_country).toLowerCase()
			);
			if (match) form.value.billing_country = match.code;
		}
	} catch (e) {
		// First-time users have no ERPNext Customer yet — backend returns
		// empty fields, so any "not found" here is unexpected. Log but
		// leave the form in its defaults.
		logger.warn("Failed to load billing details:", e);
	} finally {
		loading.value = false;
	}
}

async function save() {
	// Normalise before validating so a phone typed with spaces is not rejected
	// for punctuation we were about to strip anyway.
	form.value.billing_phone = normalisePhone(form.value.billing_phone);
	form.value.gstin = String(form.value.gstin || "").trim().toUpperCase();

	const errors = validateBillingForm(form.value);
	fieldErrors.value = errors;
	const firstBad = Object.keys(FIELD_IDS).find((f) => errors[f]);
	if (firstBad) {
		// Land the cursor on the first problem rather than leaving the user to
		// hunt for it — the form is long enough that a message can be offscreen.
		await nextTick();
		focusField(firstBad);
		return;
	}

	saving.value = true;
	saveError.value = "";
	saveSuccess.value = false;
	try {
		await api.billing.saveBillingDetails({ ...form.value });
		saveSuccess.value = true;
		emit("saved", { ...form.value });
		setTimeout(() => {
			saveSuccess.value = false;
		}, 3000);
	} catch (e) {
		const message = e instanceof Error ? e.message : String(e);
		// The server names the offending input on its response; attach the
		// message there instead of stranding it in a banner the user has to map
		// onto a field themselves. Anything unattributed stays form-level.
		const field = e?.field;
		if (field && FIELD_IDS[field]) {
			fieldErrors.value = { ...fieldErrors.value, [field]: message };
			await nextTick();
			focusField(field);
		} else {
			saveError.value = message;
		}
	} finally {
		saving.value = false;
	}
}

onMounted(load);
</script>

<style scoped>
.billing-details {
	padding-top: 1.5rem;
}
.details-header {
	margin-bottom: 1.5rem;
}
.details-title {
	font-size: 1.05rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0 0 0.35rem 0;
}
.details-description {
	font-size: 0.875rem;
	color: var(--ql-text-muted);
	margin: 0;
}
.skeleton {
	color: var(--ql-text-muted);
	padding: 1rem 0;
}
.gate-banner {
	display: flex;
	align-items: flex-start;
	gap: 0.6rem;
	padding: 0.75rem 1rem;
	margin-bottom: 1.25rem;
	background: rgba(245, 158, 11, 0.12);
	color: #92400e;
	border: 1px solid rgba(245, 158, 11, 0.35);
	border-radius: 0.5rem;
	font-size: 0.875rem;
	line-height: 1.4;
}
.gate-icon {
	width: 1.1rem;
	height: 1.1rem;
	flex-shrink: 0;
	margin-top: 0.1rem;
}
.details-form {
	max-width: 640px;
	display: flex;
	flex-direction: column;
	gap: 1rem;
}
.form-row {
	display: grid;
	grid-template-columns: 1fr 1fr;
	gap: 1rem;
}
.field-error {
	font-size: 0.8rem;
	color: #ef4444;
	margin-top: 0.35rem;
}
.tax-preview {
	font-size: 0.85rem;
	color: var(--ql-text);
	background: var(--ql-accent-soft);
	border-left: 3px solid var(--ql-accent);
	padding: 0.65rem 0.9rem;
	border-radius: 0.35rem;
	margin: 0.5rem 0 0;
}
.save-success {
	font-size: 0.85rem;
	color: #16a34a;
	margin-top: 0.35rem;
}
.save-btn {
	align-self: flex-start;
	padding: 0.65rem 1.2rem;
	font-size: 0.9rem;
	font-weight: 600;
	background: var(--ql-accent);
	color: white;
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: background 0.15s ease;
}
.save-btn:hover:not(:disabled) {
	background: var(--ql-accent-hover);
}
.save-btn:disabled {
	opacity: 0.6;
	cursor: not-allowed;
}
</style>
