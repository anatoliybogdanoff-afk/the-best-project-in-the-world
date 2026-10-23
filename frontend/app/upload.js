// Если фронтенд и сервер работают на одном адресе — оставляем ''.
// Если сервер Маши отдельно — сюда ставим выданный ею адрес,
// например: 'https://адрес-сервера', без слеша в конце.
const API_BASE = '';

const input = document.getElementById('sourceFiles');
const list = document.getElementById('sourceFilesList');
const status = document.getElementById('importStatus');
const clear = document.getElementById('clearSourceFiles');
const run = document.getElementById('runImportButton');

const allowed = new Set([
  'xml', 'json', 'yaml', 'yml', 'tab', 'xlsx', 'csv', 'pdf'
]);

let files = [];
let sending = false;

function updateControls() {
  input.disabled = sending;
  clear.hidden = files.length === 0;
  clear.disabled = sending;

  run.disabled = sending || files.length === 0;
  run.textContent = sending ? 'Отправляем файлы…' : 'Запустить анализ';

  for (const button of list.querySelectorAll('button')) {
    button.disabled = sending;
  }
}

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
      if (sending) return;

      files.splice(index, 1);
      renderFiles();
    });

    item.append(name, remove);
    list.append(item);
  });

  status.textContent = [
    files.length
      ? `Выбрано файлов: ${files.length} из 15.`
      : 'Файлы не выбраны.',
    message
  ].filter(Boolean).join(' ');

  updateControls();
}

input.addEventListener('change', () => {
  if (sending) return;

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
  if (sending) return;

  files = [];
  input.value = '';
  renderFiles();
});

run.addEventListener('click', async () => {
  if (sending || files.length === 0) return;

  sending = true;
  updateControls();
  status.textContent = 'Отправляем файлы на сервер. Не закрывайте страницу.';

  // Сбрасываем ссылку на предыдущее задание.
  delete run.dataset.jobId;

  try {
    const formData = new FormData();

    for (const file of files) {
      formData.append('files', file);
    }

    const response = await fetch(`${API_BASE}/api/imports`, {
      method: 'POST',
      body: formData
    });

    const data = await response.json().catch(() => null);

    if (!response.ok) {
      let message = `Ошибка сервера: HTTP ${response.status}.`;

      if (typeof data?.error === 'string') {
        message = data.error;
      } else if (typeof data?.detail === 'string') {
        message = data.detail;
      } else if (response.status === 404) {
        message = 'Адрес /api/imports не найден. Проверьте адрес и настройку сервера.';
      } else if (response.status === 413) {
        message = 'Размер файлов превышает ограничение сервера.';
      }

      throw new Error(message);
    }

    if (!data || typeof data.job_id !== 'string' || !data.job_id) {
      throw new Error(
        'Сервер не вернул job_id. Нужно проверить формат ответа с бэкендом.'
      );
    }

    run.dataset.jobId = data.job_id;

    status.textContent =
      `Сервер принял файлы. Номер задания: ${data.job_id}. ` +
      'Результат анализа ещё не получен.';

    // Событие для следующего этапа — отслеживания обработки.
    document.dispatchEvent(new CustomEvent('import:accepted', {
      detail: { jobId: data.job_id }
    }));
  } catch (error) {
    status.textContent = error instanceof TypeError
      ? 'Не удалось получить ответ сервера. Проверьте адрес, подключение и CORS. ' +
        'Перед повторной отправкой уточните, было ли создано задание.'
      : error.message;
  } finally {
    sending = false;
    updateControls();
  }
});

renderFiles();