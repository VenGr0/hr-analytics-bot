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

# Мок: перевод NL->SQL
def nl_to_sql_stub(text: str) -> str:
    # Это только пример. Лучше использовать LLM + prompt template.
    if 'текуч' in text.lower() or 'текучесть' in text.lower():
        return "SELECT strftime('%Y-%m', hire_date) AS ym,\n       COUNT(*) FILTER (WHERE termination_date IS NOT NULL) AS terminations,\n       COUNT(*) FILTER (WHERE termination_date IS NULL) AS active\nFROM hr_data\nGROUP BY ym\nORDER BY ym;"
    return "SELECT * FROM hr_data LIMIT 100;"
