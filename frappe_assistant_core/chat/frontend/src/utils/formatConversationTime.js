/** Clock time (e.g. "3:07 PM") for a sidebar row; "" when the date is missing or invalid. */
export function formatConversationTime(dateStr) {
	if (!dateStr) return "";
	const date = new Date(dateStr);
	if (isNaN(date.getTime())) return "";
	return date.toLocaleTimeString("en-US", {
		hour: "numeric",
		minute: "2-digit",
		hour12: true,
	});
}
