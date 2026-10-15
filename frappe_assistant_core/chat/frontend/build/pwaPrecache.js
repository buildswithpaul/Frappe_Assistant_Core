// Which build files the service worker precaches. Precaching every chunk would
// download the whole 6 MB build on install, most of it diagram renderers that
// load only when a chat contains a diagram. So the precache holds what the
// first screen needs, read from Vite's build manifest; the service worker
// caches every other chunk the first time it is used.

// Not code chunks: always precached when the build emits them.
const STATIC_FILE = /\.(woff2|png|svg|webmanifest|html)$/;

/** Files reachable from the entry through static imports, with their CSS and assets. */
export function firstScreenFiles(viteManifest) {
	const files = new Set();
	const visit = (key) => {
		const chunk = viteManifest[key];
		if (!chunk || files.has(chunk.file)) return;
		files.add(chunk.file);
		for (const file of [...(chunk.css || []), ...(chunk.assets || [])]) files.add(file);
		for (const imported of chunk.imports || []) visit(imported);
	};
	for (const [key, chunk] of Object.entries(viteManifest)) {
		if (chunk.isEntry) visit(key);
	}
	return files;
}

/** Keep precache entries for first-screen files and static files; drop the rest. */
export function keepFirstScreen(entries, viteManifest, urlPrefix) {
	const keep = firstScreenFiles(viteManifest);
	return entries.filter((entry) => {
		const file = entry.url.startsWith(urlPrefix) ? entry.url.slice(urlPrefix.length) : entry.url;
		return keep.has(file) || STATIC_FILE.test(file);
	});
}
