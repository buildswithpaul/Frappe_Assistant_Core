import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { createHistory, useBuilderShortcuts } from "@/composables/useBuilderShortcuts";

describe("createHistory", () => {
	it("undoes and redoes graph snapshots", () => {
		const history = createHistory();
		history.reset("A");
		history.record("B");
		history.record("C");

		expect(history.undo()).toBe("B");
		expect(history.undo()).toBe("A");
		expect(history.undo()).toBeNull();
		expect(history.redo()).toBe("B");
		expect(history.redo()).toBe("C");
	});

	it("ignores a record that changed nothing", () => {
		const history = createHistory();
		history.reset("A");
		history.record("A");
		expect(history.canUndo).toBe(false);
	});

	it("drops the oldest entry past the limit", () => {
		const history = createHistory({ limit: 2 });
		history.reset("A");
		history.record("B");
		history.record("C");
		history.record("D");
		expect(history.undo()).toBe("C");
		expect(history.undo()).toBe("B");
		expect(history.undo()).toBeNull();
	});

	it("drops the redo branch once a new state is recorded", () => {
		const history = createHistory();
		history.reset("A");
		history.record("B");
		history.undo();
		history.record("C");
		expect(history.canRedo).toBe(false);
	});
});

function mountShortcuts(handlers) {
	let api;
	const wrapper = mount({
		setup() {
			api = useBuilderShortcuts(handlers);
			return () => null;
		},
	});
	return { wrapper, api };
}

function key(overrides = {}) {
	return {
		key: "s",
		metaKey: false,
		ctrlKey: false,
		shiftKey: false,
		target: document.body,
		preventDefault: vi.fn(),
		...overrides,
	};
}

describe("useBuilderShortcuts", () => {
	it("saves on Cmd+S and swallows the browser dialog", () => {
		const onSave = vi.fn();
		const { api } = mountShortcuts({ onSave });
		const event = key({ key: "s", metaKey: true });
		api.handleKeydown(event);
		expect(onSave).toHaveBeenCalled();
		expect(event.preventDefault).toHaveBeenCalled();
	});

	it("separates undo from redo by the shift key", () => {
		const onUndo = vi.fn();
		const onRedo = vi.fn();
		const { api } = mountShortcuts({ onUndo, onRedo });
		api.handleKeydown(key({ key: "z", metaKey: true }));
		api.handleKeydown(key({ key: "z", metaKey: true, shiftKey: true }));
		expect(onUndo).toHaveBeenCalledTimes(1);
		expect(onRedo).toHaveBeenCalledTimes(1);
	});

	it("never steals a keystroke aimed at a text field", () => {
		const onSave = vi.fn();
		const onFitView = vi.fn();
		const { api } = mountShortcuts({ onSave, onFitView });
		const input = document.createElement("textarea");
		api.handleKeydown(key({ key: "s", metaKey: true, target: input }));
		api.handleKeydown(key({ key: "f", target: input }));
		expect(onSave).not.toHaveBeenCalled();
		expect(onFitView).not.toHaveBeenCalled();
	});

	it("still delivers Escape from inside a field", () => {
		const onEscape = vi.fn();
		const { api } = mountShortcuts({ onEscape });
		const input = document.createElement("input");
		api.handleKeydown(key({ key: "Escape", target: input }));
		expect(onEscape).toHaveBeenCalled();
	});

	it("does nothing at all when disabled (read-only viewer)", () => {
		const onSave = vi.fn();
		const { api } = mountShortcuts({ onSave, isEnabled: () => false });
		api.handleKeydown(key({ key: "s", metaKey: true }));
		expect(onSave).not.toHaveBeenCalled();
	});

	it("opens node config from the keyboard only when a node is selected", () => {
		const onOpenConfig = vi.fn().mockReturnValue(false);
		const { api } = mountShortcuts({ onOpenConfig });
		const event = key({ key: "Enter" });
		api.handleKeydown(event);
		expect(onOpenConfig).toHaveBeenCalled();
		expect(event.preventDefault).not.toHaveBeenCalled();
	});

	it("removes its listener on unmount", () => {
		const onSave = vi.fn();
		const { wrapper } = mountShortcuts({ onSave });
		wrapper.unmount();
		window.dispatchEvent(new KeyboardEvent("keydown", { key: "s", metaKey: true }));
		expect(onSave).not.toHaveBeenCalled();
	});
});
