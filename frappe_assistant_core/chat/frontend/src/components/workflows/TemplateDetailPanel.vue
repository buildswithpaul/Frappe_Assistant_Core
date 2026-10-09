<template>
	<transition name="slide">
		<div v-if="template" class="panel-backdrop" @click.self="close">
			<div class="detail-panel">
				<!-- Detail mode -->
				<template v-if="!showImport">
					<TemplateDetailBody
						ref="bodyRef"
						:template="template"
						@rate="submitRating"
						@close="close"
					/>
					<TemplateDetailFooter
						:template="template"
						@report="showReport = true"
						@download="downloadJson"
						@use="showImport = true"
					/>

					<!-- Report modal -->
					<TemplateReportModal
						:show="showReport"
						:template-name="template.name || template.template_name"
						@close="showReport = false"
						@reported="showReport = false"
					/>
				</template>

				<!-- Import mode -->
				<template v-else>
					<TemplateImportStep
						:template="template"
						:is-busy="isBusy"
						@back="showImport = false"
						@close="close"
						@import="handleImport"
					/>
				</template>
			</div>
		</div>
	</transition>
</template>

<script setup>
import { ref, watch } from "vue";
import { useWorkflowStore } from "@/stores/workflowStore";
import { __ } from "@/utils/i18n";
import { useToast } from "@/composables/useToast";
import { logger } from "@/utils/logger";
import TemplateImportStep from "./TemplateImportStep.vue";
import TemplateDetailBody from "./marketplace/TemplateDetailBody.vue";
import TemplateDetailFooter from "./marketplace/TemplateDetailFooter.vue";
import TemplateReportModal from "./TemplateReportModal.vue";

const { showError, showSuccess } = useToast();

const props = defineProps({
	template: { type: Object, default: null },
	startInImportMode: { type: Boolean, default: false },
});

const emit = defineEmits(["close", "created", "rated"]);

const store = useWorkflowStore();

const showImport = ref(false);
const showReport = ref(false);
const isBusy = ref(false);
const bodyRef = ref(null);

// Reset state when template changes
watch(
	() => props.template,
	(tpl) => {
		if (tpl) {
			showImport.value = props.startInImportMode;
		}
	}
);

function close() {
	showImport.value = false;
	bodyRef.value?.resetForm();
	emit("close");
}

async function submitRating({ rating, review }) {
	if (!rating || !props.template) return;
	try {
		const result = await store.rateTemplate(
			props.template.name || props.template.template_name,
			rating,
			review
		);
		emit("rated", result);
		bodyRef.value?.onRatingComplete();
	} catch (err) {
		logger.error("Failed to submit rating:", err);
		showError(__("Could not save your rating: {0}", [err?.userMessage || __("Something went wrong")]));
		bodyRef.value?.onRatingComplete();
	}
}

async function downloadJson() {
	if (!props.template) return;
	try {
		await store.downloadTemplate(props.template.name || props.template.template_name);
	} catch (err) {
		logger.error("Failed to download template:", err);
	}
}

async function handleImport({ name, variables }) {
	if (isBusy.value) return;
	isBusy.value = true;
	try {
		// `template.name` is the AR Marketplace Listing id (what import_listing
		// expects). `template_name` is the human-readable title — only used
		// as a fallback for legacy callers that pre-date the listing wrapper.
		const listingName = props.template.name || props.template.template_name;
		const result = await store.importTemplate(listingName, name, variables);
		// import_listing returns `{ target_doctype, target_name, listing, import_log }`.
		// Older payload variants (legacy template endpoints) returned `{ workflow: { name } }`
		// or `{ name }` — keep them as fallbacks so this works against both backends.
		const workflowName = result?.target_name || result?.workflow?.name || result?.name;
		if (workflowName) {
			showSuccess(__("Agent imported. Opening builder…"));
			emit("created", workflowName);
			// Don't call close() here — parent will navigate away, unmounting this panel
		} else {
			logger.error("Import succeeded but no workflow name returned:", result);
			showError(
				__("Import finished but no agent id was returned. Please refresh and check your agents list.")
			);
			close();
		}
	} catch (err) {
		logger.error("Failed to import template:", err);
		showError(friendlyImportError(err));
	} finally {
		isBusy.value = false;
	}
}

function friendlyImportError(err) {
	// Server messages from Frappe come back tagged with HTTP_<code> from the
	// SDK and may include HTML (e.g. <strong>) and the leading "Error: " from
	// the FACO wrapper. Strip those so the toast reads cleanly.
	const raw = err?.message || err?.toString?.() || __("Something went wrong.");
	let stripped = raw.replace(/^Error:\s*/i, "").replace(/\[HTTP_\d+\]\s*/g, "");
	// To a fixpoint: one pass over nested tags can splice a new tag together
	// out of the surrounding text.
	let previous;
	do {
		previous = stripped;
		stripped = stripped.replace(/<\/?[^>]+>/g, "");
	} while (stripped !== previous);
	stripped = stripped.trim();
	if (/workflow name must be unique/i.test(stripped)) {
		return __("An agent with this name already exists. Pick a different name and try again.");
	}
	if (/listing not found/i.test(stripped)) {
		return __("This template is no longer available in the marketplace.");
	}
	if (/plan/i.test(stripped) && /upgrade/i.test(stripped)) {
		return stripped;
	}
	return stripped || __("We couldn't import this template. Please try again.");
}
</script>

<style scoped>
.panel-backdrop {
	position: fixed;
	inset: 0;
	z-index: 1040;
	display: flex;
	justify-content: flex-end;
}

.detail-panel {
	width: 100%;
	max-width: 28rem;
	height: 100%;
	background: var(--ql-surface);
	border-left: 1px solid var(--ql-border);
	display: flex;
	flex-direction: column;
	box-shadow: -8px 0 30px rgba(0, 0, 0, 0.15);
}

/* Slide transition */
.slide-enter-active,
.slide-leave-active {
	transition: transform 0.25s ease, opacity 0.25s ease;
}

.slide-enter-from {
	transform: translateX(100%);
	opacity: 0;
}

.slide-leave-to {
	transform: translateX(100%);
	opacity: 0;
}

.slide-enter-from .detail-panel,
.slide-leave-to .detail-panel {
	transform: translateX(100%);
}

@media (max-width: 640px) {
	.detail-panel {
		max-width: 100%;
	}
}
</style>
