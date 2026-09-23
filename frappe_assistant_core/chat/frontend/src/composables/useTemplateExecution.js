import { ref } from "vue";
import { useTemplateStore } from "@/stores/templateStore";
import { logger } from "@/utils/logger";

/**
 * Encapsulates the prompt-template picker + parameter modal flow.
 *
 * Returns modal state refs plus handlers for opening the browser, choosing a
 * template, and submitting its arguments. The final rendered prompt is written
 * into `pendingPrompt`, which the caller binds to its input component so the
 * user can review/edit before sending.
 */
export function useTemplateExecution() {
	const templateStore = useTemplateStore();

	const showTemplateBrowser = ref(false);
	const showParameterModal = ref(false);
	const selectedTemplate = ref(null);
	const pendingPrompt = ref("");

	function openTemplateBrowser() {
		showTemplateBrowser.value = true;
	}

	function closeTemplateBrowser() {
		showTemplateBrowser.value = false;
	}

	function useTemplate(template) {
		// Close browser modal if open
		showTemplateBrowser.value = false;

		// Check if template has required arguments
		if (template.arguments && template.arguments.length > 0) {
			selectedTemplate.value = template;
			showParameterModal.value = true;
		} else {
			// No arguments needed, execute directly
			executeTemplate(template, {});
		}
	}

	async function submitParameters({ template, arguments: args }) {
		showParameterModal.value = false;
		selectedTemplate.value = null;
		await executeTemplate(template, args);
	}

	function closeParameterModal() {
		showParameterModal.value = false;
		selectedTemplate.value = null;
	}

	async function executeTemplate(template, args) {
		try {
			// Get the rendered prompt from the API
			const result = await templateStore.getRenderedPrompt(template.name, args);

			if (result && result.prompt) {
				// Populate the input box instead of auto-sending — lets the user
				// review and edit before sending
				pendingPrompt.value = result.prompt;
			}
		} catch (error) {
			logger.error("Failed to execute template:", error);
		}
	}

	return {
		// state
		showTemplateBrowser,
		showParameterModal,
		selectedTemplate,
		pendingPrompt,
		// handlers
		openTemplateBrowser,
		closeTemplateBrowser,
		useTemplate,
		submitParameters,
		closeParameterModal,
	};
}
