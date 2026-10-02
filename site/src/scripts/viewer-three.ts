/** three.js scene for the family-page viewer; loaded on demand by `viewer.ts`. */
import {
  Box3,
  type BufferGeometry,
  Color,
  DirectionalLight,
  GridHelper,
  HemisphereLight,
  Mesh,
  MeshStandardMaterial,
  PerspectiveCamera,
  Scene as ThreeScene,
  Vector3,
  WebGLRenderer,
} from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';

const GRID_MM = 42;
const VIEW_DIRECTION = new Vector3(0.9, -1.4, 0.95).normalize();

export type SceneOptions = { autoRotate: boolean; grid: boolean; wireframe: boolean };

export type Scene = {
  load: (part: { title: string; stl: string }, color: string) => Promise<void>;
  setColor: (color: string) => void;
  setWireframe: (on: boolean) => void;
  setAutoRotate: (on: boolean) => void;
  setGrid: (on: boolean) => void;
  resetView: () => void;
};

function createRenderer(stage: HTMLElement): WebGLRenderer {
  const renderer = new WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.domElement.setAttribute('role', 'img');
  stage.append(renderer.domElement);
  return renderer;
}

function makeGrid(spanMm: number): GridHelper {
  const cells = Math.max(2, Math.ceil(spanMm / GRID_MM) + 2);
  const grid = new GridHelper(cells * GRID_MM, cells, 0x8a8a8a, 0x8a8a8a);
  grid.rotation.x = Math.PI / 2;
  for (const material of [grid.material].flat()) {
    material.transparent = true;
    material.opacity = 0.45;
  }
  return grid;
}

/** Center the part on XY with its lowest point at z = 0, like the generator does. */
function seat(geometry: BufferGeometry): Box3 {
  geometry.computeBoundingBox();
  const box = geometry.boundingBox ?? new Box3();
  const center = box.getCenter(new Vector3());
  geometry.translate(-center.x, -center.y, -box.min.z);
  geometry.computeBoundingBox();
  geometry.computeVertexNormals();
  return geometry.boundingBox ?? box;
}

export function createScene(stage: HTMLElement, status: HTMLElement, options: SceneOptions): Scene {
  const renderer = createRenderer(stage);
  const scene = new ThreeScene();
  const camera = new PerspectiveCamera(35, 1, 1, 5000);
  camera.up.set(0, 0, 1);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.autoRotate = options.autoRotate;
  controls.autoRotateSpeed = 1.5;

  scene.add(new HemisphereLight(0xffffff, 0x445566, 1.6));
  const sun = new DirectionalLight(0xffffff, 1.8);
  sun.position.set(120, -200, 260);
  scene.add(sun);

  const material = new MeshStandardMaterial({ roughness: 0.55, metalness: 0.05 });
  material.wireframe = options.wireframe;
  let mesh: Mesh | null = null;
  let grid: GridHelper | null = null;
  let showGrid = options.grid;
  let bounds = new Box3(new Vector3(-20, -20, 0), new Vector3(20, 20, 20));
  let loadId = 0;

  const resetView = (): void => {
    const size = bounds.getSize(new Vector3());
    const radius = Math.max(size.length() / 2, 10);
    const distance = radius / Math.sin((camera.fov * Math.PI) / 360);
    controls.target.set(0, 0, size.z / 2);
    camera.position.copy(controls.target).addScaledVector(VIEW_DIRECTION, distance * 1.05);
    camera.near = distance / 100;
    camera.far = distance * 10;
    camera.updateProjectionMatrix();
    controls.update();
  };

  const resize = (): void => {
    const { clientWidth, clientHeight } = stage;
    if (clientWidth === 0 || clientHeight === 0) {
      return;
    }
    renderer.setSize(clientWidth, clientHeight, false);
    camera.aspect = clientWidth / clientHeight;
    camera.updateProjectionMatrix();
  };
  new ResizeObserver(resize).observe(stage);
  resize();

  let visible = true;
  new IntersectionObserver((entries) => {
    visible = entries.some((entry) => entry.isIntersecting);
  }).observe(stage);
  renderer.setAnimationLoop(() => {
    if (visible) {
      controls.update();
      renderer.render(scene, camera);
    }
  });

  const load = async (part: { title: string; stl: string }, color: string): Promise<void> => {
    loadId += 1;
    const id = loadId;
    status.textContent = `Loading ${part.title}…`;
    renderer.domElement.setAttribute('aria-label', `3D view of ${part.title}`);
    try {
      const geometry = await new STLLoader().loadAsync(part.stl);
      if (id !== loadId) {
        geometry.dispose();
        return;
      }
      bounds = seat(geometry);
      if (mesh) {
        scene.remove(mesh);
        mesh.geometry.dispose();
      }
      material.color = new Color(color);
      mesh = new Mesh(geometry, material);
      scene.add(mesh);
      if (grid) {
        scene.remove(grid);
        grid.dispose();
      }
      const size = bounds.getSize(new Vector3());
      grid = makeGrid(Math.max(size.x, size.y));
      grid.visible = showGrid;
      scene.add(grid);
      resetView();
      status.textContent = '';
    } catch (error) {
      if (id === loadId) {
        status.textContent = `Could not load ${part.title} (${String(error)}). Use the STL download below instead.`;
      }
    }
  };

  return {
    load,
    setColor: (color) => {
      material.color = new Color(color);
    },
    setWireframe: (on) => {
      material.wireframe = on;
    },
    setAutoRotate: (on) => {
      controls.autoRotate = on;
    },
    setGrid: (on) => {
      showGrid = on;
      if (grid) {
        grid.visible = on;
      }
    },
    resetView,
  };
}
