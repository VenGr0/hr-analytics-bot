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
    import re


    # Приоритет 1: Рекомендации по найму для конкретного отдела - гибкая логика
    if 'нанимать' in text_lower and ('отдел' in text_lower or ('сколько' in text_lower and any(dept in text_lower for dept in ['hr', 'sales', 'engineering', 'marketing', 'finance']))):
            # Сначала попробуем regex, если не сработает - fallback на поиск отдела в тексте
            department_match = re.search(r'отдел[e]?\s+(\w+)', text_lower)
            if department_match:
                dept_input = department_match.group(1).lower()

                # Маппинг названия отдела к правильному регистру из данных
                dept_mapping = {
                    'hr': 'HR',
                    'sales': 'Sales',
                    'engineering': 'Engineering',
                    'marketing': 'Marketing',
                    'finance': 'Finance'
                }
                dept = dept_mapping.get(dept_input, department_match.group(1).title())
            else:
                # Fallback: найдем отдел в запросе
                dept = None
                for d in ['hr', 'sales', 'engineering', 'marketing', 'finance']:
                    if d in text_lower:
                        dept_mapping = {
                            'hr': 'HR',
                            'sales': 'Sales',
                            'engineering': 'Engineering',
                            'marketing': 'Marketing',
                            'finance': 'Finance'
                        }
                        dept = dept_mapping[d]
                        break

            if dept:
                return f"""
SELECT
    '{dept}' AS department,
    COUNT(*) FILTER (WHERE termination_date IS NOT NULL AND department = '{dept}') AS total_terminations,
    COUNT(*) FILTER (WHERE department = '{dept}') AS total_employees,
    ROUND(100.0 * COUNT(*) FILTER (WHERE termination_date IS NOT NULL AND department = '{dept}') / NULLIF(COUNT(*) FILTER (WHERE department = '{dept}'), 0), 1) AS attrition_rate,
    CEIL(COUNT(*) FILTER (WHERE termination_date IS NOT NULL AND department = '{dept}') * 1.1) AS recommended_hiring_target,
    ROUND(AVG(CASE WHEN termination_date IS NOT NULL AND department = '{dept}' THEN service ELSE NULL END), 1) AS avg_tenure_terminated
FROM hr_data
WHERE department = '{dept}';
"""

    # Приоритет 2: Доля категорий людей уволившихся по возрасту и сервису - расширенное распознавание
    elif ('дол' in text_lower or 'какого' in text_lower or 'чаще' in text_lower) and ('возраст' in text_lower or 'категори' in text_lower) and 'сервис' in text_lower:
        # Сначала попробуем выделить номер сервиса (например "сервис 5", "сервисе в HR")
        service_match = re.search(r'сервис[e]?\s*(?:в\s*)?(\d+)', text_lower)
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
WHERE termination_date IS NOT NULL AND service IS NOT NULL
GROUP BY age_group
ORDER BY service_percentage DESC;
"""
        else:
            # Разбираем запрос с отделом вместо числа сервиса
            dept_match = re.search(r'сервис[e]?\s*(?:отдел[e]?|в)\s*(\w+)', text_lower)
            if dept_match:
                dept_input = dept_match.group(1).lower()
                dept_mapping = {
                    'hr': 'HR',
                    'sales': 'Sales',
                    'engineering': 'Engineering',
                    'marketing': 'Marketing',
                    'finance': 'Finance'
                }
                dept = dept_mapping.get(dept_input, dept_input.title())

                return f"""
SELECT '{dept}' AS department,
    CASE
        WHEN age < 25 THEN '<25'
        WHEN age BETWEEN 25 AND 34 THEN '25-34'
        WHEN age BETWEEN 35 AND 44 THEN '35-44'
        WHEN age BETWEEN 45 AND 54 THEN '45-54'
        ELSE '55+'
    END AS age_group,
    COUNT(*) AS total_terminations_in_dept,
    SUM(CASE WHEN age < 25 THEN 1 ELSE 0 END) AS under_25_terminations,
    SUM(CASE WHEN age BETWEEN 25 AND 34 THEN 1 ELSE 0 END) AS young_adult_terminations,
    SUM(CASE WHEN age BETWEEN 35 AND 44 THEN 1 ELSE 0 END) AS middle_age_terminations,
    SUM(CASE WHEN age BETWEEN 45 AND 54 THEN 1 ELSE 0 END) AS experienced_terminations,
    SUM(CASE WHEN age >= 55 THEN 1 ELSE 0 END) AS senior_terminations,
    ROUND(AVG(age), 1) AS avg_age_who_left
FROM hr_data
WHERE termination_date IS NOT NULL AND department = '{dept}'
GROUP BY department
UNION ALL
SELECT '{dept}' AS department,
    'Статистика по возрасту' AS age_group,
    NULL AS total_terminations_in_dept,
    NULLIF(COUNT(*) FILTER (WHERE age < 25), 0) AS under_25_terminations,
    NULLIF(COUNT(*) FILTER (WHERE age BETWEEN 25 AND 34), 0) AS young_adult_terminations,
    NULLIF(COUNT(*) FILTER (WHERE age BETWEEN 35 AND 44), 0) AS middle_age_terminations,
    NULLIF(COUNT(*) FILTER (WHERE age BETWEEN 45 AND 54), 0) AS experienced_terminations,
    NULLIF(COUNT(*) FILTER (WHERE age >= 55), 0) AS senior_terminations,
    ROUND(AVG(CASE WHEN age IS NOT NULL THEN age END), 1) AS avg_age_who_left
FROM hr_data
WHERE termination_date IS NOT NULL AND department = '{dept}';
"""

    # Приоритет 3: Текучесть в отделе N - расширенное распознавание
    elif ('текуч' in text_lower or 'текучесть' in text_lower):
        # Сначала попробуем найти отдел, если не найдено - любая текучесть
        department_match = re.search(r'отдел[e]? (\w+)', text_lower)
        if department_match:
            dept_input = department_match.group(1).lower()
            dept_mapping = {
                'hr': 'HR',
                'sales': 'Sales',
                'engineering': 'Engineering',
                'marketing': 'Marketing',
                'finance': 'Finance'
            }
            dept = dept_mapping.get(dept_input, department_match.group(1).title())
            return f"""
SELECT '{dept}' AS department,
    COUNT(*) FILTER (WHERE termination_date IS NOT NULL) AS total_terminations,
    COUNT(*) AS total_employees,
    ROUND(100.0 * COUNT(*) FILTER (WHERE termination_date IS NOT NULL) / NULLIF(COUNT(*), 0), 2) AS attrition_rate
FROM hr_data
WHERE department = '{dept}';
"""
        else:
            # Fallback: найдем отдел в тексте запроса
            for d in ['hr', 'sales', 'engineering', 'marketing', 'finance']:
                if d in text_lower:
                    dept_mapping = {
                        'hr': 'HR',
                        'sales': 'Sales',
                        'engineering': 'Engineering',
                        'marketing': 'Marketing',
                        'finance': 'Finance'
                    }
                    dept = dept_mapping[d]
                    return f"""
SELECT '{dept}' AS department,
    COUNT(*) FILTER (WHERE termination_date IS NOT NULL) AS total_terminations,
    COUNT(*) AS total_employees,
    ROUND(100.0 * COUNT(*) FILTER (WHERE termination_date IS NOT NULL) / NULLIF(COUNT(*), 0), 2) AS attrition_rate
FROM hr_data
WHERE department = '{dept}';
"""

    # Приоритет 4: Общая текучесть за прошлый год
    elif ('текуч' in text_lower or 'текучесть' in text_lower) and ('прошл' in text_lower or 'год' in text_lower):
        return """
SELECT
    2024 AS year,
    COUNT(*) FILTER (WHERE termination_date IS NOT NULL) AS total_terminations,
    COUNT(*) AS total_employees,
    ROUND(100.0 * COUNT(*) FILTER (WHERE termination_date IS NOT NULL) / NULLIF(COUNT(*), 0), 2) AS attrition_rate
FROM hr_data
WHERE strftime('%Y', hire_date) <= '2024';
"""

    # ДОБАВИМ ОБЩИЙ ФАЛЛБЕК ДЛЯ НАЙМА ПО ДРУГИМ ОТДЕЛАМ - ЕСЛИ НЕ ПОПАЛИ В ОСНОВНЫЕ ПАТТЕРНЫ
    # Попробуем найти любое название отдела в запросе
    dept_fallback = None
    for dept in ['sales', 'marketing', 'engineering', 'finance', 'hr']:
        if dept in text_lower:
            dept_mapping = {
                'hr': 'HR',
                'sales': 'Sales',
                'engineering': 'Engineering',
                'marketing': 'Marketing',
                'finance': 'Finance'
            }
            dept_fallback = dept_mapping[dept]
            break

    if dept_fallback and ('нанимать' in text_lower or 'сколько' in text_lower):
        return f"""
SELECT
    '{dept_fallback}' AS department,
    COUNT(*) FILTER (WHERE termination_date IS NOT NULL AND department = '{dept_fallback}') AS total_terminations,
    COUNT(*) FILTER (WHERE department = '{dept_fallback}') AS total_employees,
    ROUND(100.0 * COUNT(*) FILTER (WHERE termination_date IS NOT NULL AND department = '{dept_fallback}') / NULLIF(COUNT(*) FILTER (WHERE department = '{dept_fallback}'), 0), 1) AS attrition_rate,
    CEIL(COUNT(*) FILTER (WHERE termination_date IS NOT NULL AND department = '{dept_fallback}') * 1.1) AS recommended_hiring_target,
    ROUND(AVG(CASE WHEN termination_date IS NOT NULL AND department = '{dept_fallback}' THEN service ELSE NULL END), 1) AS avg_tenure_terminated
FROM hr_data
WHERE department = '{dept_fallback}';
"""

    # ФИННЫЙ ШТРИХ - РАСПОЗНАЕМ ЛЮБОЙ ЗАПРОС СЕРВИС+ВОЗРАСТ С ЛЮБЫМ ОТДЕЛОМ
    if 'сервис' in text_lower and 'возраст' in text_lower:
        print(f"DEBUG: FINAL CATCH - Age-service query: '{text_lower}'")

        # Определяем отдел по ключевым словам в запросе
        target_dept = None
        dept_keywords = {
            'hr': 'HR',
            'sales': 'Sales',
            'marketing': 'Marketing',
            'engineering': 'Engineering',
            'finance': 'Finance'
        }

        for keyword, dept_name in dept_keywords.items():
            if keyword in text_lower:
                target_dept = dept_name
                print(f"DEBUG: Detected department: {target_dept}")
                break

        # Если отдел не найден, возвращаем только HR
        if not target_dept:
            target_dept = 'HR'
            print("DEBUG: No department specified, defaulting to HR")

        return f"""
SELECT
    CASE
        WHEN age < 25 THEN 'до 25 лет'
        WHEN age BETWEEN 25 AND 34 THEN '25-34 года'
        WHEN age BETWEEN 35 AND 44 THEN '35-44 года'
        WHEN age BETWEEN 45 AND 54 THEN '45-54 года'
        ELSE '55+ лет'
    END AS age_category,
    COUNT(*) AS total_terminations,
    ROUND(AVG(age), 1) AS avg_age_in_group,
    ROUND(MIN(age), 0) AS min_age_in_group,
    ROUND(MAX(age), 0) AS max_age_in_group
FROM hr_data
WHERE termination_date IS NOT NULL AND department='{target_dept}'
GROUP BY age_category
ORDER BY total_terminations DESC;
"""

    # DEFAULT FALLBACK
    print(f"DEBUG: No pattern matched for: '{text_lower}'")
    return "SELECT * FROM hr_data LIMIT 5;"

    return "SELECT * FROM hr_data LIMIT 20;"
