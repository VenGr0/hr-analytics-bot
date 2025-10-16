import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import os

st.title("HR Analytics Bot — HR Insight")

# Upload CSV
uploaded_file = st.file_uploader("Upload HR Data CSV", type="csv")
data_path = None
if uploaded_file:
    data_path = f"data/{uploaded_file.name}"
    if not os.path.exists("data"):
        os.makedirs("data")
    with open(data_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    st.success(f"File uploaded: {data_path}")

# Load sample data for demo
sample_path = "data/sample.csv"
if os.path.exists(sample_path):
    if st.button("Load Sample Data"):
        data_path = sample_path
        st.success("Sample data loaded")

# Natural Language Query
nl_query = st.text_input("Enter your HR analytics question:")

if st.button("Ask Bot", key="ask"):
    if nl_query and data_path:
        payload = {"text": nl_query, "dataset_path": data_path}
        try:
            response = requests.post("http://localhost:8000/nlquery", json=payload)
            if response.status_code == 200:
                data = response.json()
                st.write("**Generated SQL:**")
                st.code(data['sql'], language='sql')
                df = pd.DataFrame(data['rows'])

                if df.empty:
                    st.warning("No data returned from query")
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

                    elif 'avg_monthly_attrition' in df.columns:
                        # Рекомендации по найму
                        st.write("### Hiring Recommendations")
                        for index, row in df.iterrows():
                            st.metric("Average Monthly Attrition", f"{int(row['avg_monthly_attrition'])}")
                            st.metric("Recommended Monthly Hiring",
                                    f"{int(row['recommended_hiring_target'])} employees")

                    # Общий insight
                    if len(df) > 0:
                        st.write("---")
                        st.write("### Insights:")
                        if 'attrition_rate' in df.columns:
                            max_rate = df['attrition_rate'].max()
                            st.write(f"🔍 Maximum attrition rate observed: {max_rate}%")
                        elif 'service_percentage' in df.columns:
                            top_group = df.loc[df['service_percentage'].idxmax()]['age_group']
                            st.write(f"👥 Age group with highest service percentage: {top_group}")
                        elif 'recommended_hiring_target' in df.columns:
                            target = int(df['recommended_hiring_target'].iloc[0])
                            st.write(f"💼 Recommended monthly target for new hires: {target} employees")
            else:
                st.error(f"API Error: {response.text}")
        except Exception as e:
            st.error(f"Connection Error: {str(e)}")
    else:
        st.warning("Please upload a CSV file or load sample data, and enter a question.")
