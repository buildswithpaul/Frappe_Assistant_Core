import { __ } from "@/utils/i18n";

// A worker that is restarting refuses a turn before saving anything and asks for it again
// (send_message / continue_response answer {status: "retry", retry_after}).
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export const restartingStatus = () => __("Server restarting, retrying…");

export async function sendWithRestartRetry(send, { wait = sleep, onRetrying = () => {} } = {}) {
	const ack = await send();
	if (ack?.status !== "retry") return ack;
	onRetrying();
	await wait(ack.retry_after * 1000);
	return send();
}

// The re-send met the restart too: the error the store raises instead of waiting on a stream.
export function restartFailure(ack) {
	if (ack?.status !== "retry") return null;
	return {
		message: __("The server is restarting. Try again in a moment."),
		code: "SERVER_RESTARTING",
	};
}
