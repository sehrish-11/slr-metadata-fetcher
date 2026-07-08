import streamlit as st
import bibtexparser
import requests
import pandas as pd
import time
import re

# Clean HTML/XML tags often found in API abstracts
def clean_abstract(text):
    if not text:
        return "No abstract found."
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

def fetch_metadata_dual_engine(doi):
    """
    Tries to fetch metadata from Crossref first. 
    If the abstract is missing, falls back to Semantic Scholar.
    """
    headers = {"User-Agent": "SLR_Metadata_Fetcher/1.0 (mailto:your_email@example.com)"}
    title, abstract = None, None

    # ---- STEP 1: TRY CROSSREF ----
    try:
        crossref_url = f"https://api.crossref.org/works/{doi}"
        response = requests.get(crossref_url, headers=headers, timeout=8)
        if response.status_code == 200:
            data = response.json()['message']
            title = data.get('title', [''])[0]
            abstract = data.get('abstract', '')
            if abstract:
                return title, clean_abstract(abstract)
    except Exception:
        pass # If Crossref fails, move quietly to fallback

    # ---- STEP 2: FALLBACK TO SEMANTIC SCHOLAR ----
    # This engine is highly reliable for Computer Science papers (ACM/IEEE)
    try:
        ss_url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=title,abstract"
        response = requests.get(ss_url, timeout=8)
        if response.status_code == 200:
            ss_data = response.json()
            if not title: 
                title = ss_data.get('title')
            ss_abstract = ss_data.get('abstract')
            if ss_abstract:
                return title, ss_abstract
    except Exception as e:
        return title if title else None, f"Both APIs failed. Error: {e}"

    # Return whatever we found, or default messages
    final_title = title if title else "Unknown Title"
    final_abstract = abstract if abstract else "Abstract not available in open databases."
    return final_title, clean_abstract(final_abstract)
