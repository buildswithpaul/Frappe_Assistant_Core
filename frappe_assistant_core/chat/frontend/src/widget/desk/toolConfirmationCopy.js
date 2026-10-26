/** What the approval card tells the user each confirmed browser tool will do. */
export const TOOL_CONFIRMATION_COPY = {
	take_screenshot: {
		action: "Capture screenshot",
		detail: "FACO wants to capture what you're looking at. The screenshot shows anything visible on screen, including personal details.",
	},
	get_form_data: {
		action: "Read form data",
		detail: "FACO wants to read every field on the open record, including its tables.",
	},
	capture_diagnostics: {
		action: "Collect page diagnostics",
		detail: "FACO wants to collect this page's recent errors, failed requests and a screenshot. They can include personal details shown on screen or named in an error.",
	},
};
