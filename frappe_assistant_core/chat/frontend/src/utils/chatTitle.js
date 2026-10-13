import { __ } from "@/utils/i18n";

/** Top-bar title: the stored title, else the server preview, else a placeholder. Never truncated. */
export function chatDisplayTitle(session, hasMessages) {
	const title = session?.title || session?.preview;
	if (title) return title;
	return hasMessages ? __("Chat") : __("New Chat");
}

/**
 * Text the rename editor opens with. Only a real title: the server fills `preview` with a
 * "New conversation" placeholder for untitled chats, which must not become a custom title.
 */
export function chatRenameSeed(session) {
	return session?.title || "";
}
