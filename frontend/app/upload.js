const input = document.getElementById('sourceFiles');
const list = document.getElementById('sourceFilesList');
const status = document.getElementById('importStatus');
const clear = document.getElementById('clearSourceFiles');

const allowed = new Set([
  'xml', 'json', 'yaml', 'yml', 'tab', 'xlsx', 'csv', 'pdf'
]);

let files = [];

function renderFiles(message = '') {
  list.replaceChildren();

  files.forEach((file, index) => {
    const item = document.createElement('li');
    const name = document.createElement('span');
    const remove = document.createElement('button');

    const size = new Intl.NumberFormat('ru-RU', {
      maximumFractionDigits: 1
    }).format(file.size / 1024);

    name.textContent = `${file.name} · ${size} КБ`;

    remove.type = 'button';
    remove.className = 'import-remove';
    remove.textContent = 'Удалить';
    remove.setAttribute('aria-label', `Удалить ${file.name}`);

    remove.addEventListener('click', () => {
      files.splice(index, 1);
      renderFiles();
    });

    item.append(name, remove);
    list.append(item);
  });

  clear.hidden = files.length === 0;

  status.textContent = [
    files.length ? `Выбрано файлов: ${files.length} из 15.` : 'Файлы не выбраны.',
    message
  ].filter(Boolean).join(' ');
}

input.addEventListener('change', () => {
  const messages = [];

  for (const file of input.files) {
    const extension = file.name.split('.').pop().toLowerCase();

    if (!allowed.has(extension)) {
      messages.push(`Неподдерживаемый формат: ${file.name}.`);
      continue;
    }

    if (file.size === 0) {
      messages.push(`Пустой файл: ${file.name}.`);
      continue;
    }

    const duplicate = files.some(existing =>
      existing.name === file.name &&
      existing.size === file.size &&
      existing.lastModified === file.lastModified
    );

    if (duplicate) {
      messages.push(`Уже выбран: ${file.name}.`);
      continue;
    }

    if (files.length >= 15) {
      messages.push('Достигнут лимит — 15 файлов.');
      break;
    }

    files.push(file);
  }

  input.value = '';
  renderFiles(messages.join(' '));
});

clear.addEventListener('click', () => {
  files = [];
  input.value = '';
  renderFiles();
});