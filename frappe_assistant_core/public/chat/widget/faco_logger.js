/**
 * FACO Widget Logger — Environment-aware logging for widget JS.
 *
 * Uses frappe.boot.developer_mode to detect environment.
 * Must be loaded AFTER faco_core.js (which sets up the FACO namespace).
 *
 * Usage:
 *   FACOLogger.error('Payment failed:', err)   // always logs
 *   FACOLogger.warn('Token expiring')           // always logs
 *   FACOLogger.debug('Socket event:', data)     // dev only
 */
(function () {
	var noop = function () {};

	var isDev = function () {
		try {
			return Boolean(frappe.boot && frappe.boot.developer_mode);
		} catch (e) {
			return false;
		}
	};

	window.FACOLogger = {
		error: function () {
			// eslint-disable-next-line no-console
			console.error.apply(console, ["[FACO]"].concat(Array.from(arguments)));
		},
		warn: function () {
			// eslint-disable-next-line no-console
			console.warn.apply(console, ["[FACO]"].concat(Array.from(arguments)));
		},
		info: function () {
			if (isDev()) {
				// eslint-disable-next-line no-console
				console.info.apply(console, ["[FACO]"].concat(Array.from(arguments)));
			}
		},
		debug: function () {
			if (isDev()) {
				// eslint-disable-next-line no-console
				console.log.apply(console, ["[FACO]"].concat(Array.from(arguments)));
			}
		},
		log: function () {
			if (isDev()) {
				// eslint-disable-next-line no-console
				console.log.apply(console, ["[FACO]"].concat(Array.from(arguments)));
			}
		},
	};
})();
