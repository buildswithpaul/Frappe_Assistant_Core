import { describe, it, expect, vi, afterEach } from "vitest";
import { mount } from "@vue/test-utils";
import { nextTick } from "vue";
import { setActivePinia, createPinia } from "pinia";
import { onComposerFiles, useFileDrop } from "./useComposerFileDrop";
import InputArea from "@/components/chat/InputArea.vue";

const makeFile = (name = "customers.csv", type = "text/csv") => new File(["a,b"], name, { type });

// A drag event as the browser fires it: a file drag lists "Files" in dataTransfer.types.
function dragEvent(files = [makeFile()], types = ["Files"]) {
	return {
		dataTransfer: { types, files, dropEffect: "none" },
		preventDefault: vi.fn(),
	};
}

let releases = [];
afterEach(() => {
	releases.forEach((release) => release());
	releases = [];
});

function composer() {
	const add = vi.fn();
	releases.push(onComposerFiles(add));
	return add;
}

describe("useFileDrop", () => {
	it("hands dropped files to the composer, as the attach button does", () => {
		const add = composer();
		const drop = useFileDrop();
		const file = makeFile();

		const event = dragEvent([file]);
		drop.onDrop(event);

		expect(event.preventDefault).toHaveBeenCalled();
		expect(add).toHaveBeenCalledWith([file]);
	});

	it("shows the overlay while files are over the area, child elements included", () => {
		composer();
		const drop = useFileDrop();

		drop.onDragEnter(dragEvent()); // the chat area
		drop.onDragEnter(dragEvent()); // a message inside it
		expect(drop.isDragging.value).toBe(true);
		drop.onDragLeave(dragEvent()); // left the message, still over the area
		expect(drop.isDragging.value).toBe(true);
		drop.onDragLeave(dragEvent()); // left the area
		expect(drop.isDragging.value).toBe(false);

		drop.onDragEnter(dragEvent());
		drop.onDrop(dragEvent());
		expect(drop.isDragging.value).toBe(false);
	});

	it("keeps the browser from opening the file in place of the chat", () => {
		composer();
		const drop = useFileDrop();
		const over = dragEvent();
		drop.onDragOver(over);
		expect(over.preventDefault).toHaveBeenCalled();
		expect(over.dataTransfer.dropEffect).toBe("copy");
	});

	it("leaves text or a link dragged inside the page to the browser", () => {
		const add = composer();
		const drop = useFileDrop();
		const text = dragEvent([], ["text/plain"]);

		drop.onDragEnter(text);
		drop.onDragOver(text);
		drop.onDrop(text);

		expect(text.preventDefault).not.toHaveBeenCalled();
		expect(drop.isDragging.value).toBe(false);
		expect(add).not.toHaveBeenCalled();
	});

	it("shows no overlay and takes nothing when no composer is on screen", () => {
		// An onboarding step: the chat area renders without a composer.
		const drop = useFileDrop();
		const enter = dragEvent();
		drop.onDragEnter(enter);
		expect(drop.isDragging.value).toBe(false);

		const dropped = dragEvent();
		drop.onDrop(dropped);
		// Still prevented: the browser would otherwise open the file in place of the chat.
		expect(dropped.preventDefault).toHaveBeenCalled();
	});

	it("gives the files to the composer on screen, not one that unmounted", () => {
		const first = vi.fn();
		const releaseFirst = onComposerFiles(first);
		const second = composer(); // the dock replaced the hero composer
		releaseFirst(); // the hero one unmounts after: it must not clear the dock's

		useFileDrop().onDrop(dragEvent());
		expect(second).toHaveBeenCalled();
		expect(first).not.toHaveBeenCalled();
	});
});

describe("InputArea takes dropped files", () => {
	it("stages a dropped file as a chip and starts its upload", async () => {
		setActivePinia(createPinia());
		const wrapper = mount(InputArea, {
			props: { isStreaming: false, interactionMode: null, context: null },
		});
		const file = makeFile();

		useFileDrop().onDrop(dragEvent([file]));
		await nextTick();

		const [files, onFailed] = wrapper.emitted("file-upload")[0];
		expect(files).toEqual([file]);
		expect(typeof onFailed).toBe("function");
		expect(wrapper.text()).toContain("customers.csv");
		wrapper.unmount();
	});

	it("refuses a dropped file of a type the server won't take, as the attach button does", async () => {
		setActivePinia(createPinia());
		const wrapper = mount(InputArea, {
			props: { isStreaming: false, interactionMode: null, context: null },
		});

		useFileDrop().onDrop(dragEvent([makeFile("setup.exe", "application/octet-stream")]));
		await nextTick();

		expect(wrapper.emitted("file-upload")).toBeUndefined();
		wrapper.unmount();
	});
});
