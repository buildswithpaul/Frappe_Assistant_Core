let panelPromise = null;

/** Load and mount the Vue panel once; later calls share it. */
export function ensurePanel(config) {
	if (!panelPromise) {
		panelPromise = import("../panel/main.js").then(({ mountPanel }) => mountPanel(config));
	}
	return panelPromise;
}
