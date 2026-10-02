import { existsSync, readFileSync } from 'node:fs';
import starlight from '@astrojs/starlight';
import { defineConfig } from 'astro/config';
import type { Catalog, DocEntry } from './src/lib/catalog-types';

function readGenerated<T>(name: string): T {
  const url = new URL(`./src/generated/${name}`, import.meta.url);
  if (!existsSync(url)) {
    throw new Error(`src/generated/${name} is missing: run \`bun run sync\` first`);
  }
  return JSON.parse(readFileSync(url, 'utf8')) as T;
}

const catalog = readGenerated<Catalog>('catalog.json');
const docs = readGenerated<DocEntry[]>('docs.json');
const hasGettingStarted = docs.some((doc) => doc.slug === 'getting-started');

const sidebar = [
  {
    label: 'Start',
    items: [
      { label: 'Home', link: '/' },
      ...(hasGettingStarted ? [{ label: 'Getting started', slug: 'docs/getting-started' }] : []),
    ],
  },
  {
    label: 'Models',
    items: [
      { label: 'Catalogue', link: '/models/' },
      { label: 'Downloads', slug: 'downloads' },
      ...catalog.families.map((family) => ({
        label: family.title,
        link: `/models/${family.module}/`,
      })),
    ],
  },
  {
    label: 'Tools',
    items: [{ label: 'Configurator', link: '/configurator/' }],
  },
  ...(docs.length > 0
    ? [
        {
          label: 'Docs',
          items: docs.map((doc) => ({ label: doc.title, slug: `docs/${doc.slug}` })),
        },
      ]
    : []),
];

export default defineConfig({
  site: 'https://micovi.github.io',
  base: '/stakee',
  trailingSlash: 'always',
  vite: {
    // three.js (~560 kB) is one lazy chunk, loaded only when a family page's viewer is shown.
    build: { chunkSizeWarningLimit: 600 },
  },
  integrations: [
    starlight({
      title: 'Stakee',
      description:
        'Parametric, stackable, 3D-printable storage for electronics hackers: crates, dividers, drawers and more.',
      social: [{ icon: 'github', label: 'GitHub', href: 'https://github.com/micovi/stakee' }],
      customCss: ['./src/styles/custom.css'],
      disable404Route: true,
      sidebar,
    }),
  ],
});
