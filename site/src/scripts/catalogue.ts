/** Client-side filtering for /models/: every control is mirrored in the URL query string. */

type Sort = 'catalogue' | 'name' | 'size';
type View = 'detailed' | 'compact';

type State = {
  q: string;
  family: string;
  material: string;
  sort: Sort;
  view: View;
};

const DEFAULTS: State = { q: '', family: '', material: '', sort: 'catalogue', view: 'detailed' };

function byId<T extends HTMLElement>(id: string, type: new () => T): T {
  const element = document.getElementById(id);
  if (!(element instanceof type)) {
    throw new Error(`catalogue: #${id} is missing or not a ${type.name}`);
  }
  return element;
}

const form = byId('catalogue-filters', HTMLFormElement);
const list = byId('catalogue', HTMLUListElement);
const count = byId('catalogue-count', HTMLSpanElement);
const reset = byId('catalogue-reset', HTMLButtonElement);
const empty = byId('catalogue-empty', HTMLParagraphElement);
const search = byId('filter-q', HTMLInputElement);
const family = byId('filter-family', HTMLSelectElement);
const material = byId('filter-material', HTMLSelectElement);
const sort = byId('filter-sort', HTMLSelectElement);
const cards = [...list.querySelectorAll<HTMLLIElement>('li.card')];

function attr(card: HTMLElement, name: string): string {
  return card.getAttribute(`data-${name}`) ?? '';
}

function optionValue(select: HTMLSelectElement, value: string): string {
  return [...select.options].some((option) => option.value === value) ? value : '';
}

function readUrl(): State {
  const params = new URLSearchParams(window.location.search);
  const sortParam = params.get('sort');
  return {
    q: params.get('q') ?? '',
    family: optionValue(family, params.get('family') ?? ''),
    material: optionValue(material, params.get('material') ?? ''),
    sort: sortParam === 'name' || sortParam === 'size' ? sortParam : 'catalogue',
    view: params.get('view') === 'compact' ? 'compact' : 'detailed',
  };
}

function readForm(): State {
  const data = new FormData(form);
  const sortValue = data.get('sort');
  return {
    q: String(data.get('q') ?? ''),
    family: String(data.get('family') ?? ''),
    material: String(data.get('material') ?? ''),
    sort: sortValue === 'name' || sortValue === 'size' ? sortValue : 'catalogue',
    view: data.get('view') === 'compact' ? 'compact' : 'detailed',
  };
}

function writeForm(state: State): void {
  search.value = state.q;
  family.value = state.family;
  material.value = state.material;
  sort.value = state.sort;
  for (const radio of form.querySelectorAll<HTMLInputElement>('input[name="view"]')) {
    radio.checked = radio.value === state.view;
  }
}

function writeUrl(state: State): void {
  const params = new URLSearchParams();
  for (const key of ['q', 'family', 'material', 'sort', 'view'] as const) {
    const value = key === 'q' ? state.q.trim() : state[key];
    if (value !== DEFAULTS[key]) {
      params.set(key, value);
    }
  }
  const query = params.toString();
  const url = `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash}`;
  window.history.replaceState(null, '', url);
}

function matches(card: HTMLElement, state: State, words: string[]): boolean {
  if (state.family && attr(card, 'family') !== state.family) {
    return false;
  }
  if (state.material && !attr(card, 'materials').split(' ').includes(state.material)) {
    return false;
  }
  const haystack = attr(card, 'search');
  return words.every((word) => haystack.includes(word));
}

function compare(sortBy: Sort): (a: HTMLElement, b: HTMLElement) => number {
  const order = (card: HTMLElement): number => Number(attr(card, 'order'));
  if (sortBy === 'name') {
    return (a, b) => attr(a, 'name').localeCompare(attr(b, 'name')) || order(a) - order(b);
  }
  if (sortBy === 'size') {
    return (a, b) => Number(attr(a, 'volume')) - Number(attr(b, 'volume')) || order(a) - order(b);
  }
  return (a, b) => order(a) - order(b);
}

function render(state: State): void {
  const words = state.q.toLowerCase().split(/\s+/).filter(Boolean);
  let shown = 0;
  for (const card of [...cards].sort(compare(state.sort))) {
    const visible = matches(card, state, words);
    card.hidden = !visible;
    shown += visible ? 1 : 0;
    list.append(card);
  }
  list.setAttribute('data-view', state.view);
  const filtered = Boolean(words.length || state.family || state.material);
  count.textContent = filtered ? `${shown} of ${cards.length} parts` : `${cards.length} parts`;
  reset.hidden = !filtered;
  empty.hidden = shown > 0;
}

function update(): void {
  const state = readForm();
  render(state);
  writeUrl(state);
}

form.addEventListener('input', update);
form.addEventListener('change', update);
form.addEventListener('submit', (event) => {
  event.preventDefault();
  update();
});
reset.addEventListener('click', () => {
  writeForm({ ...readForm(), q: '', family: '', material: '' });
  update();
  search.focus();
});

const initial = readUrl();
writeForm(initial);
render(initial);
