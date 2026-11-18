// A page's frappe as the blocks use it: call with {method, type, args} answering {message},
// db.get_doc, and datetime.str_to_user. Desk's frappe and the chat's stand-in both offer these.
export function fakeFrappe({ answers = {}, docs = [] } = {}) {
	const calls = [];
	const reads = [...docs];
	return {
		calls,
		call(opts) {
			calls.push(opts);
			const answer = answers[opts.method];
			if (answer instanceof Error) return Promise.reject(answer);
			return Promise.resolve({ message: typeof answer === "function" ? answer(opts.args) : answer });
		},
		db: {
			get_doc: () => Promise.resolve(structuredClone(reads.length > 1 ? reads.shift() : reads[0])),
		},
		datetime: { str_to_user: (value) => (value ? "13-11-2026" : "") },
	};
}
