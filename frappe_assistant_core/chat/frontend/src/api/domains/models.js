import { baseCall, getCall } from "../_core";

export const models = {
	getAvailable: () =>
		getCall("frappe_assistant_core.chat.api.get_available_models"),
	// "" clears the saved choice; the server row is what every browser and the widget read.
	setSelected: (modelId) =>
		baseCall("frappe_assistant_core.chat.api.set_selected_model", { model_id: modelId }),
};
