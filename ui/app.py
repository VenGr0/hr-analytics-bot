import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import os

st.title("HR Analytics Bot — HR Insight")

# Upload CSV
uploaded_file = st.file_uploader("Загрузить CSV файл с данными HR", type="csv")
data_path = None
if uploaded_file:
    data_path = f"data/{uploaded_file.name}"
    if not os.path.exists("data"):
        os.makedirs("data")
    with open(data_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    st.success(f"Файл загружен: {data_path}")

# Load sample data for demo
sample_path = "data/sample.csv"
if os.path.exists(sample_path):
    if st.button("Загрузить пример данных"):
        data_path = sample_path
        st.success("Пример данных загружен")

# Natural Language Query
nl_query = st.text_input("Введите ваш вопрос по HR аналитике:")

if st.button("Спросить бота", key="ask"):
    if nl_query and data_path:
        payload = {"text": nl_query, "dataset_path": data_path}
        try:
            response = requests.post("http://localhost:8000/nlquery", json=payload)
            if response.status_code == 200:
                data = response.json()
                st.write("**Сгенерированный SQL:**")
                st.code(data['sql'], language='sql')
                df = pd.DataFrame(data['rows'])

                if df.empty:
                    st.warning("Данные по запросу не найдены")
                else:
                    st.dataframe(df)

                    # Визуализации в зависимости от типа запроса
                    if 'year' in df.columns and 'attrition_rate' in df.columns:
                        # Текучесть по годам/отделам
                        fig = px.bar(df, x='year', y='attrition_rate', title="Attrition Rate")
                        st.plotly_chart(fig)

                    elif 'ym' in df.columns:
                        # Текучесть по месяцам
                        if 'terminations' in df.columns and 'active' in df.columns:
                            fig = px.line(df, x='ym', y=['terminations', 'active'],
                                        title="Terminations and Active Employees Over Time")
                            st.plotly_chart(fig)
                        elif 'monthly_terminations' in df.columns:
                            fig = px.bar(df, x='ym', y='monthly_terminations',
                                        title="Monthly Terminations")
                            st.plotly_chart(fig)

                    elif 'age_group' in df.columns and 'service_percentage' in df.columns:
                        # Распределение по возрастным группам и сервису
                        fig = px.pie(df, values='total_terminations', names='age_group',
                                   title="Terminations by Age Group")
                        st.plotly_chart(fig)

                        fig2 = px.bar(df, x='age_group', y='service_percentage',
                                    title="Service Level Percentage by Age Group")
                        st.plotly_chart(fig2)

                    elif 'recommended_hiring_target' in df.columns:
                        # Рекомендации по найму для конкретного отдела
                        dept_name = df.get('department', ['Unknown'])[0]
                        st.write(f"### 📋 Рекомендации по найму для отдела {dept_name}")
                        for index, row in df.iterrows():
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("🗑️ Всего увольнений", f"{int(row.get('total_terminations', 0))}")
                                st.metric("👥 Всего сотрудников", f"{int(row.get('total_employees', 0))}!")
                            with col2:
                                rate = round(row.get('attrition_rate', 0), 1) if row.get('attrition_rate') else 'N/A'
                                st.metric("📊 Коэффициент текучести", f"{rate}%")
                                st.metric("🎯 Рекомендуемый план найма", f"{int(row.get('recommended_hiring_target', 0))} человек")

                        # Show only hiring insights for hiring queries
                        if 'recommended_hiring_target' in df.columns:
                            target = int(df['recommended_hiring_target'].iloc[0])
                            st.write("---")
                            st.write(f"💼 **Рекомендуемая месячная цель найма: {target} сотрудников**")
            else:
                st.error(f"Ошибка API: {response.text}")
        except Exception as e:
            st.error(f"Ошибка подключения: {str(e)}")
    else:
        st.warning("Пожалуйста, загрузите CSV файл или пример данных и введите вопрос.")
