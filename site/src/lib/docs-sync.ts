import { posix } from 'node:path';
import { blobUrl, REPO_URL, rawUrl, sitePath } from '~/lib/repo';

/** Sidebar order of the hand-written docs; any other file follows, alphabetically. */
export const DOC_ORDER = [
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
  /** Called for every link that points at a file the site cannot resolve. */
  onBrokenLink: (target: string) => void;
};

export type ParsedDoc = {
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

/** Where a link written in `docs/<file>.md` should point on the site. */
export function resolveLink(target: string, isImage: boolean, ctx: LinkContext): string {
  if (target === '' || target.startsWith('#') || target.startsWith('/') || PROTOCOL.test(target)) {
    return target;
  }
  const hashAt = target.indexOf('#');
  const pathPart = hashAt === -1 ? target : target.slice(0, hashAt);
  const anchor = hashAt === -1 ? '' : target.slice(hashAt);
  const repoPath = posix.normalize(posix.join('docs', pathPart));
  if (repoPath.startsWith('../')) {
    ctx.onBrokenLink(target);
    return target;
  }
  const doc = /^docs\/([^/]+)\.md$/i.exec(repoPath);
  if (doc?.[1]) {
    const slug = docSlug(doc[1]);
    if (!ctx.docSlugs.has(slug)) {
      ctx.onBrokenLink(target);
    }
    return `${sitePath(ctx.base, `docs/${slug}/`)}${anchor}`;
  }
  if (repoPath === 'models/README.md') {
    return sitePath(ctx.base, 'models/');
  }
  const family = /^models\/([^/]+)\/README\.md$/i.exec(repoPath);
  if (family?.[1]) {
    return sitePath(ctx.base, `models/${family[1]}/`);
  }
  if (isImage) {
    const isPreview = /^models\/[^/]+\/preview\/[^/]+\.svg$/.test(repoPath);
    return isPreview ? sitePath(ctx.base, repoPath) : rawUrl(repoPath);
  }
  if (repoPath === '.') {
    return REPO_URL;
  }
  return `${blobUrl(repoPath)}${anchor}`;
}

const INLINE_LINK = /(!?)\[((?:[^[\]]|\[[^[\]]*\])*)\]\(\s*(<[^>]*>|[^\s)]+)(\s+"[^"]*")?\s*\)/g;
const REFERENCE_DEF = /^(\s{0,3}\[[^\]]+\]:\s*)(<[^>]*>|\S+)(.*)$/;

function rewriteInline(text: string, ctx: LinkContext): string {
  return text.replace(
    INLINE_LINK,
    (_match, bang: string, label: string, rawTarget: string, title: string | undefined) => {
      const target = rawTarget.replace(/^<|>$/g, '');
      const resolved = resolveLink(target, bang === '!', ctx);
      return `${bang}[${rewriteInline(label, ctx)}](${resolved}${title ?? ''})`;
    },
  );
}

/** Rewrite the links of one line, leaving `inline code` spans alone. */
function rewriteLine(line: string, ctx: LinkContext): string {
  const definition = REFERENCE_DEF.exec(line);
  if (definition) {
    const [, head = '', rawTarget = '', tail = ''] = definition;
    const target = rawTarget.replace(/^<|>$/g, '');
    return `${head}${resolveLink(target, false, ctx)}${tail}`;
  }
  const spans: string[] = [];
  const masked = line.replace(/`+[^`]*`+/g, (span) => {
    spans.push(span);
    return `\uE000${spans.length - 1}\uE000`;
  });
  return rewriteInline(masked, ctx).replace(
    /\uE000(\d+)\uE000/g,
    (_match, index: string) => spans[Number(index)] ?? '',
  );
}

/** Rewrite every repo-relative link in a docs/ markdown body for the site. */
export function rewriteLinks(markdown: string, ctx: LinkContext): string {
  let fence: string | null = null;
  const out: string[] = [];
  for (const line of markdown.split('\n')) {
    const marker = /^\s*(`{3,}|~{3,})/.exec(line)?.[1];
    if (fence !== null) {
      if (marker?.startsWith(fence)) {
        fence = null;
      }
      out.push(line);
    } else if (marker) {
      fence = marker;
      out.push(line);
    } else {
      out.push(rewriteLine(line, ctx));
    }
  }
  return out.join('\n');
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
