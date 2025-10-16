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
                st.dataframe(df)
                # Simple viz example
                if 'ym' in df.columns and not df.empty:
                    fig = px.line(df, x='ym', y=['terminations', 'active'], title="Terminations and Active Employees")
                    st.plotly_chart(fig)
            else:
                st.error(f"API Error: {response.text}")
        except Exception as e:
            st.error(f"Connection Error: {str(e)}")
    else:
        st.warning("Please upload a CSV file or load sample data, and enter a question.")
