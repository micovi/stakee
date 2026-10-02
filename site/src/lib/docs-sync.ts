import { existsSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join, posix } from 'node:path';
import type { DocEntry } from '~/lib/catalog-types';
import { blobUrl, REPO_URL, rawUrl, sitePath } from '~/lib/repo';

/** Sidebar order of the hand-written docs; any other file follows, alphabetically. */
const DOC_ORDER = [
  'getting-started',
  'cli',
  'system',
  'printing',
  'build',
  'adding-a-family',
] as const;

export type LinkContext = {
  /** Deploy base, `import.meta.env.BASE_URL` (e.g. `/stakee/`). */
  base: string;
  /** Slugs of the docs being synced, to report links to missing pages. */
  docSlugs: ReadonlySet<string>;
  /** Whether a repo-relative path (e.g. `stakee/core.py`) exists in the repository. */
  repoPathExists: (repoPath: string) => boolean;
  /** Called for every link the site cannot resolve, with the reason. */
  onBrokenLink: (target: string, reason: string) => void;
};

type ParsedDoc = {
  title: string;
  description: string;
  body: string;
};

export function docSlug(fileName: string): string {
  return fileName.replace(/\.md$/i, '').toLowerCase();
}

/** Doc slugs in sidebar order: `DOC_ORDER` first, then the rest alphabetically. */
export function orderDocs(slugs: Iterable<string>): string[] {
  const known: readonly string[] = DOC_ORDER;
  const rank = (slug: string): number => {
    const index = known.indexOf(slug);
    return index === -1 ? known.length : index;
  };
  return [...slugs].sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
}

/** Markdown inline syntax reduced to its text, for the page description. */
function plainText(markdown: string): string {
  return markdown
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '')
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/[`*_]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * Split a doc into title (line-1 `# H1`), description (the first paragraph) and body
 * (everything after the H1). Throws if line 1 is not an H1: that is the docs/ contract.
 */
export function parseDoc(fileName: string, text: string): ParsedDoc {
  const lines = text.replace(/\r\n/g, '\n').split('\n');
  const heading = /^#\s+(.+?)\s*#*\s*$/.exec(lines[0] ?? '');
  if (!heading?.[1]) {
    throw new Error(
      `docs/${fileName}: line 1 must be a '# Title' heading (got ${JSON.stringify(lines[0])}); ` +
        'every docs/*.md file starts with its title',
    );
  }
  const rest = lines.slice(1);
  while (rest[0]?.trim() === '') {
    rest.shift();
  }
  const paragraph: string[] = [];
  for (const line of rest) {
    if (line.trim() === '') {
      break;
    }
    paragraph.push(line);
  }
  const first = paragraph[0] ?? '';
  const isProse = !/^(#|```|~~~|[-*+] |\d+\. |>|\||<)/.test(first.trim());
  return {
    title: plainText(heading[1]),
    description: isProse ? plainText(paragraph.join(' ')) : '',
    body: rest.join('\n'),
  };
}

const PROTOCOL = /^[a-z][a-z0-9+.-]*:/i;

function isExternal(target: string): boolean {
  return (
    target === '' || target.startsWith('#') || target.startsWith('//') || PROTOCOL.test(target)
  );
}

function decodePath(path: string): string | null {
  try {
    return decodeURIComponent(path);
  } catch {
    return null;
  }
}

/** Where a link to the repo file `repoPath` (already checked to exist) points on the site. */
function siteTarget(repoPath: string, anchor: string, isImage: boolean, base: string): string {
  if (repoPath === 'models/README.md') {
    return sitePath(base, 'models/');
  }
  const family = /^models\/([^/]+)\/README\.md$/i.exec(repoPath);
  if (family?.[1]) {
    return sitePath(base, `models/${family[1]}/`);
  }
  if (isImage) {
    const isPreview = /^models\/[^/]+\/preview\/[^/]+\.svg$/.test(repoPath);
    return isPreview ? sitePath(base, repoPath) : rawUrl(repoPath);
  }
  if (repoPath === '.') {
    return REPO_URL;
  }
  return `${blobUrl(repoPath)}${anchor}`;
}

/** Where a link written in `docs/<file>.md` should point on the site. */
function resolveLink(target: string, isImage: boolean, ctx: LinkContext): string {
  if (isExternal(target)) {
    return target;
  }
  if (target.startsWith('/')) {
    ctx.onBrokenLink(target, 'absolute path; link relative to docs/ instead (e.g. cli.md)');
    return target;
  }
  const hashAt = target.indexOf('#');
  const pathPart = hashAt === -1 ? target : target.slice(0, hashAt);
  const anchor = hashAt === -1 ? '' : target.slice(hashAt);
  const repoPath = posix.normalize(posix.join('docs', pathPart));
  if (repoPath === '..' || repoPath.startsWith('../')) {
    ctx.onBrokenLink(target, 'points outside the repository');
    return target;
  }
  const decoded = decodePath(repoPath);
  if (decoded === null) {
    ctx.onBrokenLink(target, 'malformed %-escape in the path');
    return target;
  }
  const doc = /^docs\/([^/]+)\.md$/i.exec(repoPath);
  if (doc?.[1]) {
    const slug = docSlug(doc[1]);
    if (!ctx.docSlugs.has(slug)) {
      ctx.onBrokenLink(target, 'no such doc');
    }
    return `${sitePath(ctx.base, `docs/${slug}/`)}${anchor}`;
  }
  if (!ctx.repoPathExists(decoded)) {
    ctx.onBrokenLink(target, `${decoded} does not exist in the repository`);
    return target;
  }
  return siteTarget(repoPath, anchor, isImage, ctx.base);
}

/** A link destination as Markdown: `<...>` when it contains whitespace. */
function formatTarget(target: string): string {
  return /\s/.test(target) ? `<${target}>` : target;
}

const INLINE_LINK = /(!?)\[((?:[^[\]]|\[[^[\]]*\])*)\]\(\s*(<[^>]*>|[^\s)]+)(\s+"[^"]*")?\s*\)/g;
/** `[label]: target`; `[^note]:` is a footnote, not a link definition. */
const REFERENCE_DEF = /^(\s{0,3}\[(?!\^)[^\]]+\]:\s*)(<[^>]*>|\S+)(.*)$/;
/** A code span: a backtick run, then content, then a run of the same length. */
const CODE_SPAN = /(`+)(.*?[^`])\1(?!`)/g;

function unwrap(rawTarget: string): string {
  return rawTarget.replace(/^<|>$/g, '');
}

function rewriteInline(text: string, ctx: LinkContext): string {
  return text.replace(
    INLINE_LINK,
    (_match, bang: string, label: string, rawTarget: string, title: string | undefined) => {
      const resolved = resolveLink(unwrap(rawTarget), bang === '!', ctx);
      return `${bang}[${rewriteInline(label, ctx)}](${formatTarget(resolved)}${title ?? ''})`;
    },
  );
}

/** Rewrite the links of one line, leaving `inline code` spans alone. */
function rewriteLine(line: string, ctx: LinkContext): string {
  const definition = REFERENCE_DEF.exec(line);
  if (definition) {
    const [, head = '', rawTarget = '', tail = ''] = definition;
    return `${head}${formatTarget(resolveLink(unwrap(rawTarget), false, ctx))}${tail}`;
  }
  const spans: string[] = [];
  const masked = line.replace(CODE_SPAN, (span) => {
    spans.push(span);
    return `${spans.length - 1}`;
  });
  return rewriteInline(masked, ctx).replace(
    /(\d+)/g,
    (_match, index: string) => spans[Number(index)] ?? '',
  );
}

type BlockState = {
  /** Opening marker of the fenced code block we are in, if any. */
  fence: string | null;
  indentedCode: boolean;
  /** Inside a list, where 4-space indented lines continue an item instead of starting code. */
  inList: boolean;
  prevBlank: boolean;
};

const FENCE_OPEN = /^\s*(`{3,}|~{3,})/;
const LIST_ITEM = /^\s{0,3}([-*+]|\d{1,9}[.)])(\s|$)/;
const HEADING = /^#{1,6}(\s|$)/;

function indentWidth(line: string): number {
  let width = 0;
  for (const char of line) {
    if (char === ' ') {
      width += 1;
    } else if (char === '\t') {
      width += 4 - (width % 4);
    } else {
      break;
    }
  }
  return width;
}

function closesFence(line: string, fence: string): boolean {
  const marker = /^\s*(`+|~+)\s*$/.exec(line)?.[1];
  return marker !== undefined && marker[0] === fence[0] && marker.length >= fence.length;
}

function isIndentedCode(
  line: string,
  blank: boolean,
  prevBlank: boolean,
  state: BlockState,
): boolean {
  if (state.indentedCode) {
    return blank || indentWidth(line) >= 4;
  }
  return !blank && prevBlank && !state.inList && indentWidth(line) >= 4;
}

function updateList(line: string, prevBlank: boolean, state: BlockState): void {
  if (LIST_ITEM.test(line)) {
    state.inList = true;
  } else if (indentWidth(line) === 0 && (prevBlank || HEADING.test(line))) {
    state.inList = false;
  }
}

/** Whether `line` belongs to a fenced or indented code block; advances `state`. */
function isCodeLine(line: string, state: BlockState): boolean {
  const blank = line.trim() === '';
  const prevBlank = state.prevBlank;
  state.prevBlank = blank;
  if (state.fence !== null) {
    if (closesFence(line, state.fence)) {
      state.fence = null;
    }
    return true;
  }
  state.indentedCode = isIndentedCode(line, blank, prevBlank, state);
  if (state.indentedCode || blank) {
    return state.indentedCode;
  }
  const fence = FENCE_OPEN.exec(line)?.[1];
  if (fence) {
    state.fence = fence;
    return true;
  }
  updateList(line, prevBlank, state);
  return false;
}

/** Rewrite every repo-relative link in a docs/ markdown body for the site; code is left alone. */
export function rewriteLinks(markdown: string, ctx: LinkContext): string {
  const state: BlockState = { fence: null, indentedCode: false, inList: false, prevBlank: true };
  return markdown
    .split('\n')
    .map((line) => (isCodeLine(line, state) ? line : rewriteLine(line, ctx)))
    .join('\n');
}

/** A docs/ file as a Starlight content page: frontmatter plus the rewritten body. */
export function toStarlightPage(fileName: string, text: string, ctx: LinkContext): string {
  const doc = parseDoc(fileName, text);
  const frontmatter = [
    '---',
    `title: ${JSON.stringify(doc.title)}`,
    ...(doc.description ? [`description: ${JSON.stringify(doc.description)}`] : []),
    `editUrl: ${JSON.stringify(`${REPO_URL}/edit/main/docs/${fileName}`)}`,
    '---',
    '',
  ];
  return `${frontmatter.join('\n')}${rewriteLinks(doc.body, ctx)}`;
}

export type SyncDocsOptions = {
  /** Folder holding the hand-written `*.md` docs (the repo's `docs/`). */
  docsDir: string;
  /** Folder the Starlight pages are written to; must exist. */
  outDir: string;
  base: string;
  repoPathExists: (repoPath: string) => boolean;
};

/**
 * Convert every `*.md` in `docsDir` into a Starlight page in `outDir`, in sidebar order.
 * Throws, before writing anything, if the folder is missing or any link is broken.
 */
export function syncDocs(options: SyncDocsOptions): DocEntry[] {
  if (!existsSync(options.docsDir)) {
    throw new Error(
      `sync: docs folder not found at ${options.docsDir}; the site is built from the repo's ` +
        'docs/ next to site/, so run the sync from a full checkout',
    );
  }
  const files = readdirSync(options.docsDir).filter((name) => name.toLowerCase().endsWith('.md'));
  const bySlug = new Map(files.map((name) => [docSlug(name), name]));
  const broken: string[] = [];
  const pages: { slug: string; title: string; page: string }[] = [];
  for (const slug of orderDocs(bySlug.keys())) {
    const name = bySlug.get(slug) ?? `${slug}.md`;
    const text = readFileSync(join(options.docsDir, name), 'utf8');
    const page = toStarlightPage(name, text, {
      base: options.base,
      docSlugs: new Set(bySlug.keys()),
      repoPathExists: options.repoPathExists,
      onBrokenLink: (target, reason) => broken.push(`docs/${name}: (${target}) ${reason}`),
    });
    pages.push({ slug, title: parseDoc(name, text).title, page });
  }
  if (broken.length > 0) {
    throw new Error(
      `sync: ${broken.length} broken link(s) in docs/:\n${broken.map((b) => `  ${b}`).join('\n')}`,
    );
  }
  for (const { slug, page } of pages) {
    writeFileSync(join(options.outDir, `${slug}.md`), page);
  }
  return pages.map(({ slug, title }) => ({ slug, title }));
}
