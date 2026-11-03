import { baseCall, getCall } from "../_core";

const API = "frappe_assistant_core.chat.api.imports.";

export const imports = {
	/** Where each import session stands (#34416): `{sessions: [...], steps: [{key, label}]}`. */
	progress: (sessions) => getCall(API + "import_progress", { sessions: JSON.stringify(sessions) }),

	/** A session's mapping as the review card shows it (#34415). */
	mappingReview: (session) => getCall(API + "mapping_review", { session }),

	/** One column remapped from the review card, through set_column_mapping (#34415). */
	setMappingColumn: (session, position, field) => baseCall(API + "set_mapping_column", { session, position, field }),

	/** The import approval card's file, counts, submit flag and mapping line (#34415). */
	importCard: (session) => getCall(API + "import_card", { session }),
};
