// Verifier-side node:test reporter (stdlib only).
// Usage: node --test --test-reporter=./.verifier/reporter.mjs <files...>
// Prints "RESULT PASS <file>::<test name>" / "RESULT FAIL ..." for every test (not suites).
import { basename } from 'node:path';

export default async function* reporter(source) {
  for await (const event of source) {
    const d = event.data ?? {};
    if (event.type === 'test:pass' || event.type === 'test:fail') {
      if (d.details?.type === 'suite') continue;
      const file = d.file ? basename(d.file) : '?';
      const ok = event.type === 'test:pass' && !d.skip && !d.todo;
      yield `RESULT ${ok ? 'PASS' : 'FAIL'} ${file}::${d.name}\n`;
      if (!ok && d.details?.error) {
        const err = d.details.error;
        const msg = String(err.cause?.stack ?? err.cause ?? err.message ?? err).split('\n').slice(0, 8).join('\n');
        yield `  ${msg}\n`;
      }
    } else if (event.type === 'test:diagnostic') {
      yield `# ${d.message}\n`;
    } else if (event.type === 'test:stderr' || event.type === 'test:stdout') {
      yield d.message ?? '';
    }
  }
}
