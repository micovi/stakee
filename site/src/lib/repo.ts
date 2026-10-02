export const REPO_URL = 'https://github.com/micovi/stakee';

/** Raw download URL of a repo-relative path on main. */
export function rawUrl(path: string): string {
  return `${REPO_URL}/raw/main/${path}`;
}

/** GitHub page for a repo-relative path on main. */
export function blobUrl(path: string): string {
  return `${REPO_URL}/blob/main/${path}`;
}

/** Site URL for a path below the deploy base (`import.meta.env.BASE_URL`). */
export function sitePath(base: string, path: string): string {
  const prefix = base.endsWith('/') ? base : `${base}/`;
  return `${prefix}${path.replace(/^\//, '')}`;
}
