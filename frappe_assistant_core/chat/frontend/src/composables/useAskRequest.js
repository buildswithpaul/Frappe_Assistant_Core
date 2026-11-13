import { watch } from "vue";
import { useDiscoveryStore } from "@/stores/discoveryStore";

/**
 * Your FAC's Ask and Pages: their card's button asks a question for the user. The store keeps it
 * until a new, empty chat is showing (it routes to /chat first), then it is sent like a Home
 * starter, once.
 */
export function useAskRequest({ route, messages, send }) {
	const discovery = useDiscoveryStore();
	watch(
		[() => discovery.askRequested, () => !route.params.sessionId && messages.value.length === 0],
		([request, newChat]) => {
			if (!request || !newChat) return;
			const text = discovery.takeAskRequest();
			if (text) send(text);
		},
		{ immediate: true }
	);
}
