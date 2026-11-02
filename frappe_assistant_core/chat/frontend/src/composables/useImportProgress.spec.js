import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({ api: { imports: { progress: vi.fn() } } }));
vi.mock("@/composables/useStreaming", () => ({ onSpaSocketEvent: vi.fn(() => () => {}) }));

import { api } from "@/api/client";
import { _reset, figures, onProgress, refresh, useImportProgress } from "./useImportProgress";

const importing = {
	session: "IMP-1",
	status: "Importing",
	step: "imported",
	importing: true,
	ended: false,
	data_import: "DI-1",
	total: 200,
	created: 0,
	failed: 0,
	file_name: "customers.csv",
};

beforeEach(() => {
	_reset();
	api.imports.progress.mockResolvedValue({ sessions: [importing], steps: [{ key: "read", label: "Read" }] });
});
afterEach(() => vi.useRealTimers());

describe("live import progress (#34416)", () => {
	it("reads where a session stands from the server", async () => {
		await refresh(["IMP-1"]);
		const { state } = useImportProgressInScope(["IMP-1"]);
		expect(state.sessions["IMP-1"].status).toBe("Importing");
		expect(api.imports.progress).toHaveBeenCalledWith(["IMP-1"]);
	});

	it("moves the bar on Frappe's data_import_progress, for that Data Import only", async () => {
		await refresh(["IMP-1"]);
		const { state } = useImportProgressInScope(["IMP-1"]);
		onProgress({ data_import: "DI-OTHER", current: 150, total: 200 });
		expect(state.sessions["IMP-1"].live).toBeNull();
		onProgress({ data_import: "DI-1", current: 50, total: 200, inserted: 48, updated: 0, failed: 2 });
		expect(figures(state.sessions["IMP-1"])).toMatchObject({ done: 50, total: 200, created: 48, failed: 2, percent: 25 });
	});

	it("asks the server again once the last row is in", async () => {
		vi.useFakeTimers();
		await refresh(["IMP-1"]);
		api.imports.progress.mockClear();
		onProgress({ data_import: "DI-1", current: 200, total: 200 });
		await vi.advanceTimersByTimeAsync(2000);
		expect(api.imports.progress).toHaveBeenCalledWith(["IMP-1"]);
	});

	it("shows an ended import as complete, with the server's counts", () => {
		const ended = { ...importing, status: "Completed", importing: false, ended: true, created: 198, failed: 2 };
		expect(figures(ended)).toMatchObject({ done: 200, total: 200, created: 198, failed: 2, percent: 100 });
	});
});

// useImportProgress registers an unmount hook: run it inside a component scope
import { effectScope } from "vue";
function useImportProgressInScope(names) {
	let out;
	effectScope().run(() => {
		out = useImportProgress(names);
	});
	return out;
}
