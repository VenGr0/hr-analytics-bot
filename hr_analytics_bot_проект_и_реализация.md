# HR-Analytics Bot — «HR Insight»

**Коротко:** бот-аналитик для HR, который принимает вопросы на естественном языке, выполняет запросы к единой таблице сотрудников, рассчитывает ключевые HR‑метрики (текучесть, отток по возрасту/должности/сервису, потребность в найме), строит интерактивные визуализации и выдаёт интерпретацию результатов и рекомендации. Решение ориентировано на быструю интеграцию (CSV / Excel / SQL dump), удобный веб‑интерфейс для HR и API для автоматизации.

---

## Цель проекта и его ценность

- **Практическая полезность**: автоматизация типичных HR‑запросов и вычисление метрик, которые HR-специалисты запрашивают ежедневно.
- **Техническая глубина**: сочетание NLP→SQL (безопасное), DuckDB/SQLite для аналитики, Python + FastAPI для API, интерактивная визуализация (Streamlit/React+Plotly), возможность хостинга в Яндекс.Облаке (Docker + CI).
- **Инновация**: бот не просто возвращает цифры — он формулирует выводы на естественном языке, строит прогнозы (простая модель оттока) и предлагает план найма, основанный на прогнозах и заданных целевых SLA по заполнению вакансий.

---

## Основные функции (MVP и опции)

**MVP (обязательно):**

1. Загрузка данных (CSV/Excel). Автоопределение схемы по вкладке "Описание полей".
2. Парсинг natural language запросов -> безопасный SQL / DuckDB запрос.
3. Вычисление стандартных HR метрик: текучесть (attrition), headcount, hires, terminations, tenure distribution.
4. Интерактивные графики: time-series, распределения по возрасту/сервису/отделу.
5. Авто‑интерпретация: краткий текстовый вывод с рекомендациями (напр., "в отделе X высокая текучесть у сотрудников 25-30 лет — рекомендовано... ").

**Дополнительные фишки (опционально):**

- SQL шаблоны и «песочница» (read-only), предотвращающая DROP/ALTER.
- Прогноз простейшего оттока (логистическая регрессия / survival analysis proxy) + план найма помесячно.
- Экспорт отчётов в PDF/PowerPoint.
- Slack/Telegram/Email уведомления о метриках и аномалиях.
- Multi-tenant режим для нескольких компаний.

---

## Архитектура (вкратце)

1. **Frontend**: Streamlit или React (страница с чатом + дашборды). Streamlit быстрее для MVP.
2. **Backend**: FastAPI — принимает NL запросы, переводит в SQL (через LLM/правила), выполняет DuckDB/SQLite, формирует визуализации и текстовую интерпретацию.
3. **DB/Engine**: DuckDB (встроенная аналитика, умеет читать CSV/Parquet быстро). Можно использовать PostgreSQL для прод‑режима.
4. **NLP/LLM слой**: LLM (OpenAI/локальный LLaMA/Falcon) или rule-based + small LLM. Он отвечает за перевод NL→SQL и за формулирование интерпретаций.
5. **Оркестрация**: Docker Compose (API + UI + worker);
6. **CI/CD**: GitHub Actions → Docker image → Yandex Container Registry → Yandex Cloud Run / VM.

---

## Безопасность при переводе NL→SQL

- Блокировка опасных выражений: запрет `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `ATTACH` и т.д.
- Выполнение только `SELECT` в read-only DuckDB либо в отдельном read-only контейнере.
- Ограничение сложности запроса: лимит на количество строк/время выполнения.
- SQL-шаблоны/готовые запросы для частых сценариев и fallback к готовым агрегациям при сомнениях.

---

## Структура данных и предположения

(Смотреть вкладку "Описание полей" в предоставл. таблице — в MVP мы поддерживаем основные поля: `employee_id`, `hire_date`, `termination_date`, `department`, `service`, `age`, `position`, `gender`, `salary`, `location`, `status` и т.д.)

Примеры производных полей, которые будем вычислять:

- `tenure_days = termination_date OR today - hire_date`
- `is_active = termination_date IS NULL`
- `year_month` для временных агрегаций.

---

## Примеры пользовательских запросов и ожидаемых ответов

**Ввод:** "Какая текучесть была в отделе Sales за 2024 год?" **Бот:** 1) строит SQL: `SELECT COUNT(*) FILTER (WHERE year=2024 AND termination_date IS NOT NULL)/AVG(headcount)` и возвращает значение + график по месяцам + интерпретацию и рекомендации.

**Ввод:** "Сколько людей нужно нанять каждый месяц, чтобы покрыть отток в отделе N?" **Бот:** 1) рассчитывает среднемесячный отток по отделу за выбранный период, 2) выводит план найма (округление по целым), 3) учитывает целевой запас (например, 10%).

---

## Примеры кода (MVP skeleton)

### a) `api/main.py` — FastAPI endpoint, который принимает NL и возвращает JSON с результатом

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import duckdb
import datetime

app = FastAPI()
con = duckdb.connect(database=':memory:')

class NLQuery(BaseModel):
    text: str
    dataset_path: str = None  # optional CSV upload path

# Простая безопасная проверка
FORBIDDEN = ['drop', 'delete', 'update', 'insert', 'alter', 'attach']

@app.post('/nlquery')
async def nlquery(q: NLQuery):
    # Здесь: 1) загрузка CSV в duckdb (если передан), 2) перев. NL->SQL (stub), 3) проверка безопасности, 4) выполнение
    # 1) загрузка
    if q.dataset_path:
        con.execute(f"CREATE OR REPLACE TABLE hr_data AS SELECT * FROM read_csv_auto('{q.dataset_path}')")

    # 2) NL->SQL (для MVP — простые регулярки/шаблоны, в проде — LLM)
    sql = nl_to_sql_stub(q.text)

    # 3) безопасность
    low = sql.lower()
    if any(b in low for b in FORBIDDEN):
        raise HTTPException(status_code=400, detail='Forbidden SQL operation')

    # 4) выполнить
    try:
        res = con.execute(sql).fetchdf()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Ответ: данные + небольшое summary
    return {"sql": sql, "rows": res.to_dict(orient='records')[:200]}

# Мок: перевод NL->SQL

def nl_to_sql_stub(text: str) -> str:
    # Это только пример. Лучше использовать LLM + prompt template.
    if 'текуч' in text.lower() or 'текучесть' in text.lower():
        return "SELECT strftime('%Y-%m', hire_date) AS ym,\n       COUNT(*) FILTER (WHERE termination_date IS NOT NULL) AS terminations,\n       COUNT(*) FILTER (WHERE termination_date IS NULL) AS active\nFROM hr_data\nGROUP BY ym\nORDER BY ym;"
    return "SELECT * FROM hr_data LIMIT 100;"
```

### b) `notebooks/analysis_example.ipynb` — пример аналитики в pandas/duckdb (описывается в документации)

(В документе приложения — готовые SQL запросы для вычисления "текучести", "cumulative headcount" и % увольнений по возрасту.)

---

## Пример SQL-запросов (готовые шаблоны)

**Текучесть за год (в процентах):**

```sql
WITH yearly AS (
  SELECT
    strftime('%Y', COALESCE(termination_date, DATE '9999-12-31')) AS term_year,
    COUNT(*) FILTER (WHERE termination_date IS NOT NULL AND strftime('%Y', termination_date) = '2024') AS terminations,
    COUNT(*) FILTER (WHERE strftime('%Y', hire_date) <= '2024') AS headcount
  FROM hr_data
)
SELECT (SUM(terminations)::double / NULLIF(AVG(headcount),0)) * 100 AS attrition_percent
FROM yearly;
```

**Отток по возрастным группам:**

```sql
SELECT
  CASE WHEN age < 25 THEN '<25' WHEN age BETWEEN 25 AND 34 THEN '25-34' WHEN age BETWEEN 35 AND 44 THEN '35-44' ELSE '45+' END AS age_group,
  COUNT(*) FILTER (WHERE termination_date IS NOT NULL) AS terminations,
  COUNT(*) AS total,
  100.0 * (terminations::double / NULLIF(total,0)) AS term_percent
FROM hr_data
GROUP BY age_group;
```

---

## UI / UX концепция

- **Главная страница:** краткая статистика (KPI cards: TTM attrition, current headcount, hires last month), поле для natural language запроса и кнопки быстрых фильтров.
- **Чат‑режим:** ввод вопроса -> бот отвечает текстом + прикладывает визуализацию и SQL (по желанию).
- **Exploration page:** таблица с фильтрами, экспорт и сохранённые запросы.
- **Отчёт:** генерация PDF/PowerPoint по выбранным метрикам.

---

## Демо‑сценарий (для жюри)

1. Загрузить CSV с демо‑данными (мы поставляем sample.csv).
2. Спросить: "Какая текучесть по отделу Sales за 2024?" — бот показывает график, процент и комментарий.
3. Спросить: "Сколько нужно нанимать в отделе Sales на след. 6 мес, чтобы покрыть отток?" — бот выдаёт план найма.
4. Сгенерировать PDF отчёт.

---

## План реализации и сроки (пример для 2‑недельного хакатона)

**День 1–2:** проектирование, подготовка sample данных, поднимаем skeleton FastAPI + DuckDB, загрузку CSV. **День 3–6:** реализуем NL->SQL stub, набор готовых SQL‑шаблонов, API для основных запросов, простые графики. **День 7–10:** подключаем LLM (или локальный инструктаж), дорабатываем безопасность, UX в Streamlit. **День 11–14:** тесты, Docker, деплой в Yandex Cloud, подготовка презентации и демо.

---

## Требования к окружению и deployment

- Python 3.10+; зависимости: fastapi, uvicorn, duckdb, pandas, pydantic, streamlit (опционально), plotly, scikit-learn (opt).
- Dockerfile + docker-compose для локальной демонстрации.
- Для прод: Yandex.Cloud Run or Yandex VM + Container Registry.

---

## Метрики успеха и оценки (для жюри)

- Точность переводов NL→SQL (процент корректных SQL для 20 тестовых запросов).
- Наличие минимум 5 готовых сценариев/SQL шаблонов (текучесть, churn by age, hires needed, headcount trend, tenure distribution).
- UX: скорость ответа < 3s для простых агрегаций, корректность визуализаций.
- Доп. баллы: автоматическая генерация плана найма, экспорт отчётов, интеграция с Slack.

---

## Что я подготовил здесь

- Полный план проекта и архитектуры.
- Примеры кода (FastAPI skeleton + SQL шаблоны).
- Демо‑сценарий, план реализации и требования для деплоя.

---

##
