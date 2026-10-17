// The page the Desk user is looking at, kept current across navigation. Shared by the panel
// (composer placeholder) and the welcome (page asks) so both read the same detection.
import { onMounted, onUnmounted, ref } from "vue";
import { getHost } from "./host/index.js";

export function usePageContext() {
	const pageContext = ref({});
	let stop = () => {};
	const detect = () => (pageContext.value = getHost().detectContext() || {});
	onMounted(() => {
		detect();
		stop = getHost().onContextChange(detect);
	});
	onUnmounted(() => stop());
	return { pageContext };
}
