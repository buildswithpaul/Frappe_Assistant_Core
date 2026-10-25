/** What the approval card tells the user each confirmed browser tool will do. */
export const TOOL_CONFIRMATION_COPY = {
	take_screenshot: {
		action: "Capture screenshot",
		detail: "The AI wants to capture what you're looking at and send it to the assistant. The screenshot may contain any PII visible on screen.",
	},
	get_form_data: {
		action: "Read form data",
		detail: "The AI wants to read every field on the open record (including child tables) and send it to the assistant.",
	},
	capture_diagnostics: {
		action: "Collect page diagnostics",
		detail: "The AI wants to collect this page's recent console errors, failed network requests and a screenshot, and send them to the assistant. These may contain any PII visible on screen or named in an error.",
	},
};
