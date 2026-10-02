import { mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, test } from 'vitest';
import {
  type LinkContext,
  orderDocs,
  parseDoc,
  rewriteLinks,
  syncDocs,
  toStarlightPage,
} from '~/lib/docs-sync';

/** Repo files the link tests may point at, besides the docs themselves. */
const REPO_FILES = new Set([
  'stakee/core.py',
  'tests/test_cli.py',
  'models/README.md',
  'models/crates/README.md',
  'models/kit/README.md',
  'models/kit/preview/stack-clip.svg',
  'models/kit/preview/a.svg',
  'docs/img/photo.jpg',
  'docs/my file.png',
  '.',
]);

function context(broken: string[] = []): LinkContext {
  return {
    base: '/stakee/',
    docSlugs: new Set(['cli', 'system', 'getting-started']),
    repoPathExists: (repoPath) => REPO_FILES.has(repoPath),
    onBrokenLink: (target) => broken.push(target),
  };
}

describe('orderDocs', () => {
  test('known docs first, extras alphabetical after', () => {
    expect(orderDocs(['zeta', 'system', 'alpha', 'getting-started', 'cli'])).toEqual([
      'getting-started',
      'cli',
      'system',
      'alpha',
      'zeta',
    ]);
  });

  test('empty', () => {
    expect(orderDocs([])).toEqual([]);
  });
});

describe('parseDoc', () => {
  test('title, summary and body', () => {
    const doc = parseDoc(
      'cli.md',
      '# The `stakee` CLI\n\nMake [crates](system.md) fast.\nTwo lines.\n\n## Usage\n',
    );
    expect(doc.title).toBe('The stakee CLI');
    expect(doc.description).toBe('Make crates fast. Two lines.');
    expect(doc.body).toBe('Make [crates](system.md) fast.\nTwo lines.\n\n## Usage\n');
  });

  test('no summary paragraph gives no description', () => {
    expect(parseDoc('a.md', '# A\n\n## Section\n').description).toBe('');
    expect(parseDoc('a.md', '# A\n').description).toBe('');
  });

  test('missing H1 fails with the file name', () => {
    expect(() => parseDoc('bad.md', '---\ntitle: x\n---\n')).toThrow(/docs\/bad\.md: line 1/);
    expect(() => parseDoc('empty.md', '')).toThrow(/docs\/empty\.md/);
  });
});

describe('rewriteLinks', () => {
  test.each([
    ['[cli](cli.md)', '[cli](/stakee/docs/cli/)'],
    ['[s](system.md#stacking)', '[s](/stakee/docs/system/#stacking)'],
    ['[s](./system.md)', '[s](/stakee/docs/system/)'],
    ['[c](../models/crates/README.md)', '[c](/stakee/models/crates/)'],
    ['[c](../models/crates/README.md#parts)', '[c](/stakee/models/crates/)'],
    ['[all](../models/README.md)', '[all](/stakee/models/)'],
    [
      '[core](../stakee/core.py)',
      '[core](https://github.com/micovi/stakee/blob/main/stakee/core.py)',
    ],
    [
      '[t](../tests/test_cli.py#L10 "Tests")',
      '[t](https://github.com/micovi/stakee/blob/main/tests/test_cli.py#L10 "Tests")',
    ],
    [
      '![p](../models/kit/preview/stack-clip.svg)',
      '![p](/stakee/models/kit/preview/stack-clip.svg)',
    ],
    ['![p](img/photo.jpg)', '![p](https://github.com/micovi/stakee/raw/main/docs/img/photo.jpg)'],
    ['[repo](..)', '[repo](https://github.com/micovi/stakee)'],
    ['[x](https://example.com/a.md)', '[x](https://example.com/a.md)'],
    ['[x](mailto:someone@example.com)', '[x](mailto:someone@example.com)'],
    ['[x](#local)', '[x](#local)'],
    ['[ref]: cli.md#flags', '[ref]: /stakee/docs/cli/#flags'],
    ['[ref]: <cli.md> "CLI"', '[ref]: /stakee/docs/cli/ "CLI"'],
    ['`[x](cli.md)` and [y](cli.md)', '`[x](cli.md)` and [y](/stakee/docs/cli/)'],
    ['``a ` [x](cli.md)`` and [y](cli.md)', '``a ` [x](cli.md)`` and [y](/stakee/docs/cli/)'],
    [
      '[`core.py`](../stakee/core.py)',
      '[`core.py`](https://github.com/micovi/stakee/blob/main/stakee/core.py)',
    ],
    [
      '[![p](../models/kit/preview/a.svg)](../models/kit/README.md)',
      '[![p](/stakee/models/kit/preview/a.svg)](/stakee/models/kit/)',
    ],
    ['![p](<my file.png>)', '![p](<https://github.com/micovi/stakee/raw/main/docs/my file.png>)'],
    ['![p](my%20file.png)', '![p](https://github.com/micovi/stakee/raw/main/docs/my%20file.png)'],
    ['[^1]: Some note.', '[^1]: Some note.'],
    ['[^1]: See [cli](cli.md).', '[^1]: See [cli](/stakee/docs/cli/).'],
  ])('%s', (input, expected) => {
    const broken: string[] = [];
    expect(rewriteLinks(input, context(broken))).toBe(expected);
    expect(broken).toEqual([]);
  });

  test('fenced code is left alone', () => {
    const text =
      '```md\n[cli](cli.md)\n```\n[cli](cli.md)\n~~~~\n[a](cli.md)\n~~~\n~~~~\n[b](cli.md)';
    expect(rewriteLinks(text, context())).toBe(
      '```md\n[cli](cli.md)\n```\n[cli](/stakee/docs/cli/)\n~~~~\n[a](cli.md)\n~~~\n~~~~\n' +
        '[b](/stakee/docs/cli/)',
    );
  });

  test('indented code is left alone', () => {
    const text = 'Text:\n\n    [cli](cli.md)\n\n    [ref]: cli.md\n\n[cli](cli.md)';
    expect(rewriteLinks(text, context())).toBe(
      'Text:\n\n    [cli](cli.md)\n\n    [ref]: cli.md\n\n[cli](/stakee/docs/cli/)',
    );
  });

  test('indented lines inside a list continue the item', () => {
    const text = '- item\n\n    more about [cli](cli.md)\n\n## Next\n\n    [code](cli.md)';
    expect(rewriteLinks(text, context())).toBe(
      '- item\n\n    more about [cli](/stakee/docs/cli/)\n\n## Next\n\n    [code](cli.md)',
    );
  });

  test('an indented line right after a paragraph is not code', () => {
    expect(rewriteLinks('Text\n    [cli](cli.md)', context())).toBe(
      'Text\n    [cli](/stakee/docs/cli/)',
    );
  });

  test.each([
    ['[b](../../outside.md)', '../../outside.md'],
    ['[c](../stakee/missing.py)', '../stakee/missing.py'],
    ['![d](img/missing.png)', 'img/missing.png'],
    ['[e](/docs/cli/)', '/docs/cli/'],
    ['[f]: ../stakee/gone.py', '../stakee/gone.py'],
    ['[g](bad%zz.md)', 'bad%zz.md'],
  ])('%s is reported as broken and left as written', (input, target) => {
    const broken: string[] = [];
    expect(rewriteLinks(input, context(broken))).toBe(input);
    expect(broken).toEqual([target]);
  });

  test('a broken doc link is still pointed at its page', () => {
    const broken: string[] = [];
    expect(rewriteLinks('[a](missing.md)', context(broken))).toBe('[a](/stakee/docs/missing/)');
    expect(broken).toEqual(['missing.md']);
  });
});

describe('toStarlightPage', () => {
  test('frontmatter replaces the H1', () => {
    const page = toStarlightPage(
      'cli.md',
      '# CLI "tool"\n\nRuns it.\n\nSee [system](system.md).\n',
      context(),
    );
    expect(page).toBe(
      [
        '---',
        'title: "CLI \\"tool\\""',
        'description: "Runs it."',
        'editUrl: "https://github.com/micovi/stakee/edit/main/docs/cli.md"',
        '---',
        'Runs it.',
        '',
        'See [system](/stakee/docs/system/).',
        '',
      ].join('\n'),
    );
  });
});

describe('syncDocs', () => {
  let root = '';
  let docsDir = '';
  let outDir = '';

  beforeEach(() => {
    root = mkdtempSync(join(tmpdir(), 'stakee-docs-'));
    docsDir = join(root, 'docs');
    outDir = join(root, 'out');
    mkdirSync(docsDir);
    mkdirSync(outDir);
  });

  afterEach(() => {
    rmSync(root, { recursive: true, force: true });
  });

  const sync = () =>
    syncDocs({
      docsDir,
      outDir,
      base: '/stakee/',
      repoPathExists: (repoPath) => REPO_FILES.has(repoPath),
    });

  test('writes one page per doc and returns them in sidebar order', () => {
    writeFileSync(join(docsDir, 'zeta.md'), '# Zeta\n\nLast.\n');
    writeFileSync(join(docsDir, 'CLI.md'), '# CLI\n\nSee [zeta](zeta.md).\n');
    writeFileSync(join(docsDir, 'notes.txt'), 'not a doc');
    expect(sync()).toEqual([
      { slug: 'cli', title: 'CLI' },
      { slug: 'zeta', title: 'Zeta' },
    ]);
    expect(readdirSync(outDir).sort()).toEqual(['cli.md', 'zeta.md']);
    expect(readFileSync(join(outDir, 'cli.md'), 'utf8')).toContain('[zeta](/stakee/docs/zeta/)');
  });

  test('broken links fail the sync, listing every file and link, and nothing is written', () => {
    writeFileSync(join(docsDir, 'a.md'), '# A\n\n[x](missing.md) [y](/abs/)\n');
    writeFileSync(join(docsDir, 'b.md'), '# B\n\n[z](../stakee/gone.py)\n');
    expect(sync).toThrow(
      [
        'sync: 3 broken link(s) in docs/:',
        '  docs/a.md: (missing.md) no such doc',
        '  docs/a.md: (/abs/) absolute path; link relative to docs/ instead (e.g. cli.md)',
        '  docs/b.md: (../stakee/gone.py) stakee/gone.py does not exist in the repository',
      ].join('\n'),
    );
    expect(readdirSync(outDir)).toEqual([]);
  });

  test('a missing docs folder is an error', () => {
    rmSync(docsDir, { recursive: true });
    expect(sync).toThrow(/docs folder not found at .*docs/);
  });
});
