<template>
	<transition name="slide">
		<div v-if="template" class="panel-backdrop" @click.self="close">
			<div class="detail-panel">
				<!-- Detail mode -->
				<template v-if="!showImport">
					<div class="panel-header">
						<div class="header-left">
							<h2 class="panel-title">{{ template.template_name || "Template" }}</h2>
							<div
								v-if="template.is_official || template.featured"
								class="title-badges"
							>
								<span v-if="template.is_official" class="badge badge-official">
									<svg
										width="12"
										height="12"
										viewBox="0 0 24 24"
										fill="currentColor"
									>
										<path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
									</svg>
									Official
								</span>
								<span v-if="template.featured" class="badge badge-featured">
									<svg width="12" height="12" viewBox="0 0 24 24" fill="#f59e0b">
										<path
											d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"
										/>
									</svg>
									Featured
								</span>
							</div>
						</div>
						<button @click="close" class="close-btn" title="Close" aria-label="Close">
							<svg
								width="18"
								height="18"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M6 18L18 6M6 6l12 12"
								/>
							</svg>
						</button>
					</div>

					<div class="panel-body">
						<!-- Meta row -->
						<div class="meta-row">
							<span class="meta-category">{{ template.category || "General" }}</span>
							<span v-if="template.version" class="meta-item"
								>v{{ template.version }}</span
							>
							<span v-if="template.author_name" class="meta-item"
								>by {{ template.author_name }}</span
							>
							<span v-if="template.import_count" class="meta-item"
								>{{ template.import_count }} import{{
									template.import_count !== 1 ? "s" : ""
								}}</span
							>
							<span
								v-if="template.min_agent_nodes"
								class="meta-item"
								:title="`This template uses ${
									template.min_agent_nodes
								} Task${
									template.min_agent_nodes !== 1 ? 's' : ''
								}. More tasks = higher credit cost per run.`"
								>{{ template.min_agent_nodes }} task{{
									template.min_agent_nodes !== 1 ? "s" : ""
								}}</span
							>
						</div>

						<!-- Description -->
						<div class="detail-section">
							<h3 class="section-label">Description</h3>
							<p class="description-text">
								{{ template.description || "No description provided." }}
							</p>
						</div>

						<!-- Rating section -->
						<TemplateRatingSection
							ref="ratingSectionRef"
							:template="template"
							:rating="template.average_rating || 0"
							@rate="submitRating"
						/>

						<!-- Tools section -->
						<div v-if="toolsList.length > 0" class="detail-section">
							<h3 class="section-label">Required Tools</h3>
							<div class="tools-list">
								<div v-for="tool in toolsList" :key="tool" class="tool-item">
									<svg
										width="12"
										height="12"
										viewBox="0 0 24 24"
										fill="none"
										stroke="currentColor"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											stroke-width="2"
											d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
										/>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											stroke-width="2"
											d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
										/>
									</svg>
									<span>{{ tool }}</span>
								</div>
							</div>
						</div>

						<!-- Variables preview -->
						<div v-if="variablesList.length > 0" class="detail-section">
							<h3 class="section-label">Configurable Variables</h3>
							<div class="variables-list">
								<div
									v-for="v in variablesList"
									:key="v.name || v"
									class="variable-item"
								>
									<span class="variable-name">{{ v.name || v }}</span>
									<span v-if="v.description" class="variable-desc">{{
										v.description
									}}</span>
								</div>
							</div>
						</div>
					</div>

					<!-- Review status (for own templates) -->
					<div
						v-if="template.review_status && template.review_status !== 'Approved'"
						class="review-status-bar"
					>
						<span
							:class="[
								'review-badge',
								`review-${(template.review_status || '')
									.toLowerCase()
									.replace(/ /g, '-')}`,
							]"
						>
							{{ template.review_status }}
						</span>
						<p
							v-if="template.review_notes && template.review_status === 'Rejected'"
							class="review-reason"
						>
							{{ template.review_notes }}
						</p>
					</div>

					<div class="panel-footer">
						<button
							v-if="template.is_public && !template.is_official"
							class="btn-report"
							@click="showReport = true"
							title="Report template"
						>
							<svg
								width="14"
								height="14"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M3 21v-4m0 0V5a2 2 0 012-2h6.5l1 1H21l-3 6 3 6h-8.5l-1-1H5a2 2 0 00-2 2z"
								/>
							</svg>
							Report
						</button>
						<div class="footer-right">
							<button class="btn-secondary" @click="downloadJson">
								<svg
									width="14"
									height="14"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
								>
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
									/>
								</svg>
								Download JSON
							</button>
							<button class="btn-primary" @click="showImport = true">
								Use This Template
							</button>
						</div>
					</div>

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
import { ref, computed, watch } from "vue";
import { useWorkflowStore } from "@/stores/workflowStore";
import { useToast } from "@/composables/useToast";
import { logger } from "@/utils/logger";
import TemplateImportStep from "./TemplateImportStep.vue";
import TemplateRatingSection from "./marketplace/TemplateRatingSection.vue";
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
const ratingSectionRef = ref(null);

// Reset state when template changes
watch(
	() => props.template,
	(tpl) => {
		if (tpl) {
			showImport.value = props.startInImportMode;
		}
	}
);

const toolsList = computed(() => {
	if (!props.template) return [];
	const tools = props.template.required_tools || props.template.tool_hints;
	if (!tools) return [];
	if (Array.isArray(tools)) return tools;
	if (typeof tools === "string") {
		try {
			return JSON.parse(tools);
		} catch {
			return [tools];
		}
	}
	return [];
});

const variablesList = computed(() => {
	if (!props.template) return [];
	const schema = props.template.variables_schema;
	if (!schema) return [];
	if (Array.isArray(schema)) return schema;
	if (typeof schema === "string") {
		try {
			const parsed = JSON.parse(schema);
			if (Array.isArray(parsed)) return parsed;
			if (parsed && typeof parsed === "object") {
				return Object.entries(parsed).map(([name, config]) => ({
					name,
					...(typeof config === "object" ? config : { description: String(config) }),
				}));
			}
		} catch {
			return [];
		}
	}
	if (typeof schema === "object") {
		return Object.entries(schema).map(([name, config]) => ({
			name,
			...(typeof config === "object" ? config : { description: String(config) }),
		}));
	}
	return [];
});

function close() {
	showImport.value = false;
	ratingSectionRef.value?.resetForm();
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
		ratingSectionRef.value?.onRatingComplete();
	} catch (err) {
		logger.error("Failed to submit rating:", err);
		ratingSectionRef.value?.onRatingComplete();
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
			showSuccess("Agent imported. Opening builder…");
			emit("created", workflowName);
			// Don't call close() here — parent will navigate away, unmounting this panel
		} else {
			logger.error("Import succeeded but no workflow name returned:", result);
			showError(
				"Import finished but no agent id was returned. Please refresh and check your agents list."
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
	const raw = err?.message || err?.toString?.() || "Something went wrong.";
	const stripped = raw
		.replace(/^Error:\s*/i, "")
		.replace(/\[HTTP_\d+\]\s*/g, "")
		.replace(/<\/?[^>]+>/g, "")
		.trim();
	if (/workflow name must be unique/i.test(stripped)) {
		return "An agent with this name already exists. Pick a different name and try again.";
	}
	if (/listing not found/i.test(stripped)) {
		return "This template is no longer available in the marketplace.";
	}
	if (/plan/i.test(stripped) && /upgrade/i.test(stripped)) {
		return stripped;
	}
	return stripped || "We couldn't import this template. Please try again.";
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

/* Header */
.panel-header {
	display: flex;
	align-items: flex-start;
	justify-content: space-between;
	padding: 1.25rem 1.25rem 1rem;
	border-bottom: 1px solid var(--ql-border);
	flex-shrink: 0;
	gap: 0.75rem;
}

.header-left {
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
	min-width: 0;
}

.panel-title {
	font-size: 1.125rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0;
	line-height: 1.3;
}

.title-badges {
	display: flex;
	gap: 0.375rem;
	flex-wrap: wrap;
}

.badge {
	display: inline-flex;
	align-items: center;
	gap: 0.2rem;
	font-size: 0.625rem;
	font-weight: 600;
	padding: 0.125rem 0.375rem;
	border-radius: 9999px;
	text-transform: uppercase;
	letter-spacing: 0.03em;
}

.badge-official {
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
}

.badge-featured {
	background: rgba(245, 158, 11, 0.1);
	color: #f59e0b;
}

.close-btn {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 28px;
	height: 28px;
	background: transparent;
	border: none;
	color: var(--ql-text-muted);
	border-radius: 0.25rem;
	cursor: pointer;
	transition: all 0.15s ease;
	flex-shrink: 0;
}

.close-btn:hover {
	background: var(--ql-subtle);
	color: var(--ql-text);
}

/* Body */
.panel-body {
	flex: 1;
	overflow-y: auto;
	padding: 1.25rem;
	display: flex;
	flex-direction: column;
	gap: 1.25rem;
}

/* Meta */
.meta-row {
	display: flex;
	flex-wrap: wrap;
	align-items: center;
	gap: 0.5rem;
}

.meta-category {
	font-size: 0.6875rem;
	font-weight: 600;
	padding: 0.125rem 0.5rem;
	border-radius: 9999px;
	text-transform: uppercase;
	letter-spacing: 0.03em;
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
}

.meta-item {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.meta-item::before {
	content: "\00b7";
	margin-right: 0.5rem;
}

/* Sections */
.detail-section {
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
}

.section-label {
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.04em;
	margin: 0;
}

.description-text {
	font-size: 0.8125rem;
	color: var(--ql-text);
	line-height: 1.6;
	margin: 0;
	white-space: pre-wrap;
}

/* Tools */
.tools-list {
	display: flex;
	flex-direction: column;
	gap: 0.375rem;
}

.tool-item {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
	padding: 0.375rem 0.625rem;
	background: var(--ql-bg);
	border-radius: 0.375rem;
}

.tool-item svg {
	color: var(--ql-text-muted);
	flex-shrink: 0;
}

/* Variables */
.variables-list {
	display: flex;
	flex-direction: column;
	gap: 0.375rem;
}

.variable-item {
	display: flex;
	flex-direction: column;
	gap: 0.125rem;
	padding: 0.5rem 0.625rem;
	background: var(--ql-bg);
	border-radius: 0.375rem;
}

.variable-name {
	font-size: 0.8125rem;
	font-weight: 600;
	color: var(--ql-text);
	font-family: monospace;
}

.variable-desc {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

/* Review status */
.review-status-bar {
	padding: 0.625rem 1.25rem;
	border-top: 1px solid var(--ql-border);
}
.review-badge {
	font-size: 0.6875rem;
	font-weight: 600;
	padding: 0.125rem 0.5rem;
	border-radius: 9999px;
	text-transform: uppercase;
	letter-spacing: 0.03em;
}
.review-pending-review {
	background: rgba(245, 158, 11, 0.12);
	color: #d97706;
}
.review-rejected {
	background: rgba(239, 68, 68, 0.12);
	color: #dc2626;
}
.review-suspended {
	background: rgba(239, 68, 68, 0.12);
	color: #dc2626;
}
.review-reason {
	font-size: 0.75rem;
	color: var(--ql-danger);
	margin: 0.375rem 0 0;
}

/* Footer */
.panel-footer {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 0.625rem;
	padding: 1rem 1.25rem;
	border-top: 1px solid var(--ql-border);
	flex-shrink: 0;
}
.footer-right {
	display: flex;
	align-items: center;
	gap: 0.625rem;
}
.btn-report {
	display: inline-flex;
	align-items: center;
	gap: 0.25rem;
	padding: 0.375rem 0.625rem;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	background: transparent;
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	cursor: pointer;
}
.btn-report:hover {
	color: var(--ql-danger);
	border-color: var(--ql-danger);
}

/* Buttons */
.btn-primary {
	display: inline-flex;
	align-items: center;
	gap: 0.375rem;
	padding: 0.5rem 1rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: white;
	background: var(--ql-accent);
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.btn-primary:hover:not(:disabled) {
	opacity: 0.9;
}
.btn-primary:disabled {
	opacity: 0.5;
	cursor: default;
}

.btn-secondary {
	display: inline-flex;
	align-items: center;
	gap: 0.375rem;
	padding: 0.5rem 1rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.btn-secondary:hover {
	border-color: var(--ql-text);
}

/* Spinner */
.loading-spinner {
	width: 1rem;
	height: 1rem;
	border: 2px solid rgba(255, 255, 255, 0.3);
	border-top-color: white;
	border-radius: 50%;
	animation: spin 0.8s linear infinite;
}

.loading-spinner.small {
	width: 0.875rem;
	height: 0.875rem;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

@media (max-width: 640px) {
	.detail-panel {
		max-width: 100%;
	}

	.panel-footer {
		flex-direction: column;
	}

	.panel-footer .btn-primary,
	.panel-footer .btn-secondary {
		width: 100%;
		justify-content: center;
	}
}
</style>
