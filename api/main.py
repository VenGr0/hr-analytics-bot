from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import duckdb
import os

app = FastAPI()
con = duckdb.connect(database=':memory:')

class NLQuery(BaseModel):
    text: str
    dataset_path: str  # required CSV path

# Простая безопасная проверка
FORBIDDEN = ['drop', 'delete', 'update', 'insert', 'alter', 'attach']

@app.post('/nlquery')
async def nlquery(q: NLQuery):
    # Здесь: 1) загрузка CSV в duckdb (если передан), 2) перев. NL->SQL (stub), 3) проверка безопасности, 4) выполнение
    # 1) загрузка
    if q.dataset_path and os.path.exists(q.dataset_path):
        con.execute(f"CREATE OR REPLACE TABLE hr_data AS SELECT * FROM read_csv_auto('{q.dataset_path}')")
    else:
        raise HTTPException(status_code=400, detail='Dataset file not found')

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
        raise HTTPException(status_code=400, detail=f'SQL Error: {str(e)}')

    # Ответ: данные + небольшое summary
    return {"sql": sql, "rows": res.to_dict(orient='records')[:200]}

# Расширенный перевод NL->SQL
def nl_to_sql_stub(text: str) -> str:
    text_lower = text.lower()

    # 1. Текучесть в отделе N за прошлый год
    if ('текуч' in text_lower or 'текучесть' in text_lower) and ('отдел' in text_lower or 'департамент' in text_lower):
        # Выделяем название отдела
        import re
        department_match = re.search(r'отдел[e]? (\w+)', text_lower)
        if department_match:
            dept = department_match.group(1).title()
            return f"""
SELECT
    strftime('%Y', COALESCE(termination_date, DATE '9999-12-31')) AS year,
    COUNT(*) FILTER (WHERE termination_date IS NOT NULL AND department = '{dept}') AS terminations,
    COUNT(*) FILTER (WHERE department = '{dept}') AS total_employees,
    ROUND(100.0 * terminations / NULLIF(total_employees, 0), 2) AS attrition_rate
FROM hr_data
WHERE strftime('%Y', hire_date) <= '2024'
GROUP BY year
ORDER BY year DESC
LIMIT 1;
"""

    # 2. Доля категорий людей уволившихся по возрасту и сервису
    elif ('дол' in text_lower or 'какого' in text_lower) and ('возраст' in text_lower or 'категори' in text_lower) and 'сервис' in text_lower:
        # Выделяем номер сервиса
        service_match = re.search(r'сервис[e]? (\d+)', text_lower)
        if service_match:
            service = service_match.group(1)
            return f"""
SELECT
    CASE
        WHEN age < 25 THEN '<25'
        WHEN age BETWEEN 25 AND 34 THEN '25-34'
        WHEN age BETWEEN 35 AND 44 THEN '35-44'
        WHEN age BETWEEN 45 AND 54 THEN '45-54'
        ELSE '55+'
    END AS age_group,
    COUNT(*) AS total_terminations,
    COUNT(*) FILTER (WHERE service = {service}) AS service_terminations,
    ROUND(100.0 * COUNT(*) FILTER (WHERE service = {service}) / NULLIF(COUNT(*), 0), 2) AS service_percentage
FROM hr_data
WHERE termination_date IS NOT NULL
GROUP BY age_group
ORDER BY service_percentage DESC;
"""

    # 3. Сколько необходимо нанимать для покрытия оттока в отделе
    elif ('нанимать' in text_lower or 'покрыть' in text_lower) and ('отдел' in text_lower or 'месяц' in text_lower):
        department_match = re.search(r'отдел[e]? (\w+)', text_lower)
        if department_match:
            dept = department_match.group(1).title()
            return f"""
WITH monthly_attrition AS (
    SELECT
        strftime('%Y-%m', termination_date) AS ym,
        COUNT(*) AS monthly_terminations
    FROM hr_data
    WHERE termination_date IS NOT NULL
      AND department = '{dept}'
      AND strftime('%Y', termination_date) >= strftime('%Y', 'now', '-1 year')
    GROUP BY ym
)
SELECT
    ROUND(AVG(monthly_terminations), 0) AS avg_monthly_attrition,
    ROUND(AVG(monthly_terminations) * 1.1, 0) AS recommended_hiring_target
FROM monthly_attrition;
"""

    # 4. Общая текучесть за прошлый год
    elif ('текуч' in text_lower or 'текучесть' in text_lower) and ('прошл' in text_lower or 'год' in text_lower):
        return """
SELECT
    strftime('%Y', COALESCE(termination_date, DATE '9999-12-31')) AS year,
    COUNT(*) FILTER (WHERE termination_date IS NOT NULL) AS terminations,
    COUNT(*) FILTER (WHERE termination_date IS NULL OR strftime('%Y', termination_date) = '2024') AS total_employees,
    ROUND(100.0 * terminations / NULLIF(total_employees, 0), 2) AS attrition_rate
FROM hr_data
WHERE strftime('%Y', hire_date) <= '2024'
GROUP BY year
ORDER BY year DESC
LIMIT 1;
"""

    # Default fallback
    return "SELECT * FROM hr_data LIMIT 20;"
