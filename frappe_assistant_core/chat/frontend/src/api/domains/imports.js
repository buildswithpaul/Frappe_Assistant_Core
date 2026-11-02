import { getCall } from "../_core";

export const imports = {
	/** Where each import session stands (#34416): `{sessions: [...], steps: [{key, label}]}`. */
	progress: (sessions) =>
		getCall("frappe_assistant_core.chat.api.imports.import_progress", {
			sessions: JSON.stringify(sessions),
		}),
};
