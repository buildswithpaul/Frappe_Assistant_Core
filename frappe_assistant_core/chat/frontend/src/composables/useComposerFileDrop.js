import { getCurrentInstance, onBeforeUnmount, ref } from "vue";

// The composer that takes files dropped on the chat. The SPA and the Desk widget are separate
// bundles, so each has its own; within one, a single InputArea is mounted at a time (the hero
// slot or the bottom dock).
let receiver = null;

/**
 * Let the composer take files dropped anywhere on the chat, as if picked with the attach
 * button. Call from the composer's setup; it lets go when the composer unmounts.
 */
export function onComposerFiles(add) {
	receiver = add;
	const release = () => {
		if (receiver === add) receiver = null;
	};
	if (getCurrentInstance()) onBeforeUnmount(release);
	return release;
}

const carriesFiles = (event) => Array.from(event.dataTransfer?.types || []).includes("Files");

/**
 * Drag-and-drop for an area of the chat. While files are dragged over it, `isDragging` shows
 * the drop overlay; dropped files go to the composer. Text or a link dragged inside the page
 * is left to the browser. With no composer on screen (an onboarding step) no overlay shows,
 * and a dropped file does nothing rather than the browser opening it in place of the chat.
 */
export function useFileDrop() {
	const isDragging = ref(false);
	// dragenter and dragleave fire for every child element the pointer crosses
	let depth = 0;

	function onDragEnter(event) {
		if (!carriesFiles(event)) return;
		event.preventDefault();
		depth++;
		isDragging.value = Boolean(receiver);
	}

	function onDragOver(event) {
		if (!carriesFiles(event)) return;
		event.preventDefault();
		event.dataTransfer.dropEffect = receiver ? "copy" : "none";
	}

	function onDragLeave(event) {
		if (!carriesFiles(event)) return;
		depth = Math.max(0, depth - 1);
		if (depth === 0) isDragging.value = false;
	}

	function onDrop(event) {
		depth = 0;
		isDragging.value = false;
		if (!carriesFiles(event)) return;
		event.preventDefault();
		const files = Array.from(event.dataTransfer.files || []);
		if (files.length && receiver) receiver(files);
	}

	return { isDragging, onDragEnter, onDragOver, onDragLeave, onDrop };
}
