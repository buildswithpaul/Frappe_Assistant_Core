import { __ } from "@/utils/i18n";

// One static string per combination, so translation extraction sees every sentence whole.
export function projectDeleteMessage({ documents, memory }) {
	if (documents && memory) {
		return __(
			"Delete this project? Its chats are kept, its documents move to your Knowledge Base as private documents, and its memories are deleted."
		);
	}
	if (documents) {
		return __(
			"Delete this project? Its chats are kept and its documents move to your Knowledge Base as private documents."
		);
	}
	if (memory) {
		return __("Delete this project? Its chats are kept and its memories are deleted.");
	}
	return __("Delete this project? Its chats are kept and moved out of the project.");
}
