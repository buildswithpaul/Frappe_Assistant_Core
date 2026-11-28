const isScalar = (value) => ["string", "number", "boolean"].includes(typeof value);

const SIMPLE_ESCAPES = { n: "\n", t: "\t", r: "\r", "\\": "\\", "'": "'", '"': '"', a: "\x07", b: "\b", f: "\f", v: "\v", 0: "\0" };
const HEX_ESCAPES = { x: 2, u: 4, U: 8 };

/**
 * The values in `text` when all of it is Python data as `print` writes it: lists, dicts and tuples,
 * several to a line for `print(a, b)`. Null when any of it is something else, or something this
 * could only show wrongly.
 */
export function pythonValues(text) {
	let at = 0;
	const fail = () => {
		throw new SyntaxError("not Python data");
	};
	const skipSpace = () => {
		while (/\s/.test(text[at] ?? "")) at += 1;
	};
	// Python's repr escapes every non-printable character, so each escape is decoded or the
	// whole text is refused: a half-read string would show wrong data as if it were right.
	const readEscape = () => {
		const kind = text[at];
		if (Object.hasOwn(SIMPLE_ESCAPES, kind)) return SIMPLE_ESCAPES[kind];
		const digits = text.slice(at + 1, at + 1 + (HEX_ESCAPES[kind] ?? 0));
		if (!Object.hasOwn(HEX_ESCAPES, kind) || !new RegExp(`^[0-9a-fA-F]{${HEX_ESCAPES[kind]}}$`).test(digits)) fail();
		at += digits.length;
		return String.fromCodePoint(parseInt(digits, 16));
	};
	const readString = (quote) => {
		let out = "";
		at += 1;
		while (at < text.length && text[at] !== quote) {
			if (text[at] === "\\") {
				at += 1;
				out += readEscape();
			} else out += text[at];
			at += 1;
		}
		if (text[at] !== quote) fail();
		at += 1;
		return out;
	};
	const readSequence = (close) => {
		const items = [];
		at += 1;
		for (skipSpace(); text[at] !== close; skipSpace()) {
			items.push(readValue());
			skipSpace();
			if (text[at] === ",") at += 1;
			else if (text[at] !== close) fail();
		}
		at += 1;
		return items;
	};
	const readDict = () => {
		const out = {};
		at += 1;
		for (skipSpace(); text[at] !== "}"; skipSpace()) {
			const key = readValue();
			skipSpace();
			// "__proto__" would set the object's prototype instead of a key.
			if (text[at] !== ":" || !isScalar(key) || key === "__proto__") fail();
			at += 1;
			out[key] = readValue();
			skipSpace();
			if (text[at] === ",") at += 1;
			else if (text[at] !== "}") fail();
		}
		at += 1;
		return out;
	};
	function readValue() {
		skipSpace();
		const char = text[at];
		if (char === "[") return readSequence("]");
		if (char === "(") return readSequence(")");
		if (char === "{") return readDict();
		if (char === "'" || char === '"') return readString(char);
		const word = /^(True|False|None)\b/.exec(text.slice(at, at + 6));
		if (word) {
			at += word[1].length;
			return { True: true, False: false, None: null }[word[1]];
		}
		const number = /^-?\d+(\.\d+)?([eE][-+]?\d+)?/.exec(text.slice(at, at + 40));
		if (!number) fail();
		const value = Number(number[0]);
		// A longer integer than a JS number holds would be shown with its last digits changed.
		if (/^-?\d+$/.test(number[0]) && !Number.isSafeInteger(value)) fail();
		at += number[0].length;
		return value;
	}
	try {
		const values = [];
		for (skipSpace(); at < text.length; skipSpace()) {
			const value = readValue();
			if (value === null || typeof value !== "object") fail();
			values.push(value);
		}
		return values.length ? values : null;
	} catch {
		// Not data, or nested deeper than the parser's recursion reaches.
		return null;
	}
}
