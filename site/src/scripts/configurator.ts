/** /configurator/: live command, sizes and CLI validation for `stakee box`. */
import {
  type BoxOptions,
  boxCommand,
  cavity,
  compartmentSizes,
  LABEL_MIN_HEIGHT_UNITS,
  labelTextWidth,
  labelTileCount,
  outerSize,
  railPositions,
  stackPitch,
  type Vec3,
  validate,
} from '~/lib/geometry';

const NO_COMMAND = '# fix the inputs above to get a command';

function element<T extends HTMLElement>(id: string, type: new () => T): T {
  const found = document.getElementById(id);
  if (!(found instanceof type)) {
    throw new Error(`configurator: #${id} is missing or not a ${type.name}`);
  }
  return found;
}

const mm = (value: number): string => `${Number(value.toFixed(2))}`;
const triple = (v: Vec3): string => `${mm(v.x)} × ${mm(v.y)} × ${mm(v.z)} mm`;

function readOptions(form: HTMLFormElement): BoxOptions {
  const data = new FormData(form);
  const num = (name: string): number => {
    const raw = String(data.get(name) ?? '').trim();
    return raw === '' ? Number.NaN : Number(raw);
  };
  return {
    nx: num('nx'),
    ny: num('ny'),
    h: num('h'),
    across: num('across'),
    along: num('along'),
    label: String(data.get('label') ?? ''),
    cap: data.has('cap'),
    noMagnets: data.has('noMagnets'),
    noSockets: data.has('noSockets'),
    lipClearance: num('lipClearance'),
  };
}

function resultRows(opts: BoxOptions): [string, string][] {
  const inner = cavity(opts.nx, opts.ny, opts.h);
  const rows: [string, string][] = [
    ['Outer size (W × D × H)', triple(outerSize(opts.nx, opts.ny, opts.h))],
    ['Cavity (W × D × H)', triple(inner)],
    ['Stack pitch', `${mm(stackPitch(opts.h))} mm`],
  ];
  if (opts.across > 1 || opts.along > 1) {
    const widths = compartmentSizes(inner.x, railPositions(opts.nx, opts.across));
    const depths = compartmentSizes(inner.y, railPositions(opts.ny, opts.along));
    rows.push(
      ['Compartment widths', `${widths.map(mm).join(', ')} mm`],
      ['Compartment depths', `${depths.map(mm).join(', ')} mm`],
      ['Rails', `${opts.along - 1} X rail(s), ${opts.across - 1} Y rail(s)`],
    );
  }
  if (opts.label.trim() !== '') {
    const tiles = labelTileCount(opts.cap);
    rows.push(
      [
        'Label text area',
        `${mm(labelTextWidth(outerSize(opts.nx, opts.ny, opts.h).x))} mm wide; ` +
          'the CLI shrinks long text down to a 3.5 mm font and rejects anything smaller',
      ],
      ['Label tiles', tiles === 1 ? '1, for the crate' : `${tiles}, for the crate and the cap`],
    );
  } else if (opts.h < LABEL_MIN_HEIGHT_UNITS) {
    rows.push([
      'Label',
      `none: boxes lower than ${LABEL_MIN_HEIGHT_UNITS} units have no label recess`,
    ]);
  }
  return rows;
}

function renderList<T>(target: HTMLElement, items: T[], build: (item: T) => HTMLElement[]): void {
  target.replaceChildren(...items.flatMap(build));
}

function make(tag: string, text: string): HTMLElement {
  const node = document.createElement(tag);
  node.textContent = text;
  return node;
}

/** Wire the configurator form; recomputes on every input. */
export function mountConfigurator(): void {
  const form = element('box-form', HTMLFormElement);
  const errors = element('box-errors', HTMLDivElement);
  const errorList = element('box-error-list', HTMLUListElement);
  const command = element('box-command', HTMLElement);
  const copy = element('box-copy', HTMLButtonElement);
  const copied = element('box-copied', HTMLSpanElement);
  const result = element('box-result', HTMLElement);

  const update = (): void => {
    const opts = readOptions(form);
    const problems = validate(opts);
    renderList(errorList, problems, (problem) => [make('li', problem)]);
    errors.hidden = problems.length === 0;
    for (const input of form.querySelectorAll<HTMLInputElement>('input')) {
      input.setAttribute('aria-invalid', String(!input.checkValidity()));
    }
    command.textContent = problems.length === 0 ? boxCommand(opts) : NO_COMMAND;
    copy.disabled = problems.length > 0;
    copied.textContent = '';
    const rows = problems.length === 0 ? resultRows(opts) : [];
    renderList(result, rows, ([term, value]) => [make('dt', term), make('dd', value)]);
  };

  copy.addEventListener('click', () => {
    navigator.clipboard
      .writeText(command.textContent ?? '')
      .then(() => {
        copied.textContent = 'Copied.';
      })
      .catch((error: unknown) => {
        copied.textContent = `Copy failed (${String(error)}); select the command instead.`;
      });
  });
  form.addEventListener('input', update);
  form.addEventListener('submit', (event) => event.preventDefault());
  update();
}
