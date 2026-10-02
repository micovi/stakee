/**
 * Family-page 3D viewer: wires the controls and lazy-loads three.js (`viewer-three.ts`)
 * once the stage scrolls near the viewport. Kept free of three.js imports so the page
 * itself stays light.
 */
import type { Scene } from '~/scripts/viewer-three';

export type ViewerPart = {
  slug: string;
  title: string;
  stl: string;
  color: string;
  size: string;
};

function element<T extends HTMLElement>(id: string, type: new () => T): T {
  const found = document.getElementById(id);
  if (!(found instanceof type)) {
    throw new Error(`viewer: #${id} is missing or not a ${type.name}`);
  }
  return found;
}

function hasWebGL(): boolean {
  try {
    const canvas = document.createElement('canvas');
    return Boolean(canvas.getContext('webgl2') ?? canvas.getContext('webgl'));
  } catch {
    return false;
  }
}

function readParts(root: HTMLElement): ViewerPart[] {
  const parts: unknown = JSON.parse(root.getAttribute('data-parts') ?? '[]');
  if (!Array.isArray(parts)) {
    throw new Error('viewer: data-parts is not a list');
  }
  return parts as ViewerPart[];
}

function whenNearViewport(target: HTMLElement, run: () => void): void {
  if (!('IntersectionObserver' in window)) {
    run();
    return;
  }
  const observer = new IntersectionObserver(
    (entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        observer.disconnect();
        run();
      }
    },
    { rootMargin: '300px' },
  );
  observer.observe(target);
}

type Controls = {
  part: HTMLSelectElement;
  color: HTMLInputElement;
  wireframe: HTMLInputElement;
  rotate: HTMLInputElement;
  grid: HTMLInputElement;
  reset: HTMLButtonElement;
  size: HTMLOutputElement;
  status: HTMLParagraphElement;
};

function findControls(): Controls {
  return {
    part: element('viewer-part', HTMLSelectElement),
    color: element('viewer-color', HTMLInputElement),
    wireframe: element('viewer-wireframe', HTMLInputElement),
    rotate: element('viewer-rotate', HTMLInputElement),
    grid: element('viewer-grid', HTMLInputElement),
    reset: element('viewer-reset', HTMLButtonElement),
    size: element('viewer-size', HTMLOutputElement),
    status: element('viewer-status', HTMLParagraphElement),
  };
}

function wire(scene: Scene, controls: Controls, parts: ViewerPart[]): void {
  const bySlug = new Map(parts.map((part) => [part.slug, part]));
  const show = (slug: string): void => {
    const part = bySlug.get(slug);
    if (!part) {
      return;
    }
    controls.part.value = slug;
    controls.color.value = part.color;
    controls.size.value = part.size;
    void scene.load(part, part.color);
  };
  controls.part.addEventListener('change', () => show(controls.part.value));
  controls.color.addEventListener('input', () => scene.setColor(controls.color.value));
  controls.wireframe.addEventListener('change', () =>
    scene.setWireframe(controls.wireframe.checked),
  );
  controls.rotate.addEventListener('change', () => scene.setAutoRotate(controls.rotate.checked));
  controls.grid.addEventListener('change', () => scene.setGrid(controls.grid.checked));
  controls.reset.addEventListener('click', () => scene.resetView());
  for (const button of document.querySelectorAll<HTMLButtonElement>('button.show-3d')) {
    button.addEventListener('click', () => {
      show(button.getAttribute('data-part') ?? '');
      controls.part.scrollIntoView({ block: 'center' });
      controls.part.focus({ preventScroll: true });
    });
  }
  const fromHash = decodeURIComponent(window.location.hash.slice(1));
  show(bySlug.has(fromHash) ? fromHash : controls.part.value);
}

/** Set up the viewer on a family page; shows a message instead when WebGL is unavailable. */
export function mountViewer(): void {
  const root = element('viewer-root', HTMLDivElement);
  const stage = element('viewer-stage', HTMLDivElement);
  const controls = findControls();
  const parts = readParts(root);
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  controls.rotate.checked = !reducedMotion;
  if (!hasWebGL()) {
    controls.status.textContent =
      'Your browser cannot show 3D (WebGL is unavailable). The previews and downloads below still work.';
    root.querySelector('.controls')?.setAttribute('hidden', '');
    return;
  }
  controls.status.textContent = 'Loading the 3D viewer…';
  whenNearViewport(stage, () => {
    import('~/scripts/viewer-three')
      .then(({ createScene }) => {
        const scene = createScene(stage, controls.status, {
          autoRotate: controls.rotate.checked,
          grid: controls.grid.checked,
          wireframe: controls.wireframe.checked,
        });
        wire(scene, controls, parts);
      })
      .catch((error: unknown) => {
        controls.status.textContent = `The 3D viewer failed to start: ${String(error)}`;
      });
  });
}
