import { describe, expect, test } from 'vitest';
import {
  type LinkContext,
  orderDocs,
  parseDoc,
  rewriteLinks,
  toStarlightPage,
} from '~/lib/docs-sync';

function context(broken: string[] = []): LinkContext {
  return {
    base: '/stakee/',
    docSlugs: new Set(['cli', 'system', 'getting-started']),
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
    ['[x](https://example.com/a.md)', '[x](https://example.com/a.md)'],
    ['[x](#local)', '[x](#local)'],
    ['[ref]: cli.md#flags', '[ref]: /stakee/docs/cli/#flags'],
    ['`[x](cli.md)` and [y](cli.md)', '`[x](cli.md)` and [y](/stakee/docs/cli/)'],
    [
      '[`core.py`](../stakee/core.py)',
      '[`core.py`](https://github.com/micovi/stakee/blob/main/stakee/core.py)',
    ],
    [
      '[![p](../models/kit/preview/a.svg)](../models/kit/README.md)',
      '[![p](/stakee/models/kit/preview/a.svg)](/stakee/models/kit/)',
    ],
  ])('%s', (input, expected) => {
    expect(rewriteLinks(input, context())).toBe(expected);
  });

  test('fenced code is left alone', () => {
    const text = '```md\n[cli](cli.md)\n```\n[cli](cli.md)';
    expect(rewriteLinks(text, context())).toBe(
      '```md\n[cli](cli.md)\n```\n[cli](/stakee/docs/cli/)',
    );
  });

  test('links to missing docs and outside the repo are reported', () => {
    const broken: string[] = [];
    rewriteLinks('[a](missing.md) [b](../../outside.md) [c](cli.md)', context(broken));
    expect(broken).toEqual(['missing.md', '../../outside.md']);
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
