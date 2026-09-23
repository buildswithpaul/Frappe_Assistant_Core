const FILLER = /^(hi|hey|hello|thanks|thank you|please|ok|okay|so|also|and|can you|could you|would you|will you|help me)[,!.\s]+/i;
const MAX_HEADING = 48;

export function deriveHeading(content, n) {
	let text = String(content || "").trim();
	let prev;
	do {
		prev = text;
		text = text.replace(FILLER, "").trim();
	} while (text && text !== prev);
	text = text.split(/[.?!\n]/)[0].trim();
	if (!text) return `Exchange ${n}`;
	if (text.length > MAX_HEADING) {
		const cut = text.slice(0, MAX_HEADING);
		text = cut.slice(0, cut.lastIndexOf(" ") > 20 ? cut.lastIndexOf(" ") : MAX_HEADING).trimEnd() + "…";
	}
	return text;
}

function formatTime(ts) {
	if (!ts) return "";
	const d = new Date(ts);
	if (Number.isNaN(d.getTime())) return "";
	return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function mergeAssistant(entry, msg) {
	const blocks = Array.isArray(msg.blocks) ? msg.blocks : [];
	for (const b of blocks) {
		if (b.type === "tool_call" && !b.isInternal) entry.toolCount += 1;
		if (b.type === "text" && /```chart/.test(b.content || "")) entry.hasChart = true;
		if (b.type === "generated_documents") entry.hasFiles = true;
		if (b.type === "interaction") {
			entry.approval = b.status === "pending" ? "pending" : entry.approval || "resolved";
		}
	}
	if (msg.message_id) entry.messageId = msg.message_id;
	if (msg.isStreaming) entry.streaming = true;
	else entry.completed = true;
}

export function deriveIndexEntries(messages) {
	const list = Array.isArray(messages) ? messages : [];
	const entries = [];
	let exchangeNo = 0;
	let current = null;

	const newExchange = (index, content, timestamp) => {
		exchangeNo += 1;
		current = {
			kind: "exchange",
			key: `ex-${index}`,
			index,
			messageId: null,
			heading: deriveHeading(content, exchangeNo),
			toolCount: 0,
			hasChart: false,
			hasFiles: false,
			approval: null,
			time: formatTime(timestamp),
			streaming: false,
			completed: false,
		};
		entries.push(current);
	};

	list.forEach((msg, index) => {
		if (!msg) return;
		if (msg.role === "divider") {
			entries.push({ kind: "divider", key: `div-${index}` });
			current = null;
		} else if (msg.role === "user") {
			newExchange(index, msg.content, msg.timestamp);
		} else if (msg.role === "assistant") {
			if (!current) newExchange(index, "", msg.timestamp);
			mergeAssistant(current, msg);
		}
	});
	return entries;
}

export function completedExchangeCount(entries) {
	return (entries || []).filter((e) => e.kind === "exchange" && e.completed).length;
}
