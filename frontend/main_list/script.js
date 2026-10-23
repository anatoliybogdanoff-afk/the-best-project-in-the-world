const fileInput = document.getElementById("data-file");
const analyzeButton = document.getElementById("analyze-button");
const uploadStatus = document.getElementById("upload-status");

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];

  // После каждого нового выбора сначала отключаем кнопку.
  analyzeButton.disabled = true;

  if (!file) {
    uploadStatus.textContent = "Выберите файл для начала работы.";
    return;
  }

  // accept в HTML только ограничивает выбор в окне.
  // Поэтому дополнительно проверяем расширение здесь.
  if (!file.name.toLowerCase().endsWith(".csv")) {
    uploadStatus.textContent = "Нужен файл с расширением .csv.";
    return;
  }

  if (file.size === 0) {
    uploadStatus.textContent = "Файл пустой. Выберите CSV с данными.";
    return;
  }

  uploadStatus.textContent = `Выбран файл: ${file.name}`;
  analyzeButton.disabled = false;
});

const results = document.getElementById("results");

analyzeButton.addEventListener("click", () => {
  results.hidden = false;

  uploadStatus.textContent =
    "Открыт пример результатов. Загруженный файл пока не анализировался.";

  results.scrollIntoView({
    behavior: "smooth",
    block: "start"
  });
});

// При выборе другого файла скрываем предыдущие результаты.
fileInput.addEventListener("change", () => {
  results.hidden = true;
});