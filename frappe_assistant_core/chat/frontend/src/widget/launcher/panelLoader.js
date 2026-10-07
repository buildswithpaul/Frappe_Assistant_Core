let panelPromise = null;

/**
 * Load and mount the Vue panel once; later calls share it. A failed load (a deploy swapping
 * hashed chunks, a flaky network) is not cached, so the next call retries.
 */
export function ensurePanel(config, load = () => import("../panel/main.js")) {
	if (!panelPromise) {
		panelPromise = load()
			.then(({ mountPanel }) => mountPanel(config))
			.catch((err) => {
				panelPromise = null;
				throw err;
			});
	}
	return panelPromise;
}

/** Unmount and remove the panel, if one was ever mounted, so the next ensurePanel starts fresh. */
export async function destroyPanel() {
	const pending = panelPromise;
	panelPromise = null;
	if (!pending) return;
	try {
		const panel = await pending;
		panel.destroy();
	} catch {
		// It never mounted; there is nothing to remove.
	}
}
