"""Streamlit Community Cloud entrypoint.

Streamlit Cloud defaults the "Main file path" to `streamlit_app.py`; this thin
wrapper makes that default work out of the box. The full app lives in
`dashboard.py` — running `streamlit run dashboard.py` locally is equivalent.
"""
from dashboard import main

main()
