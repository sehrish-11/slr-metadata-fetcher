import streamlit as st
import bibtexparser
import requests
import pandas as pd
import time
import re

# Clean HTML/XML/JATS tags often found in API abstracts
def clean_abstract(text):
    if not text:
        return ""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text).strip()

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
        pass  # If Crossref fails or times out, silently move to fallback

    # ---- STEP 2: FALLBACK TO SEMANTIC SCHOLAR ----
    # Highly reliable for Computer Science papers (ACM/IEEE)
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
    except Exception:
        pass

    # Fallback assignment if both engines partially failed or lacked data
    final_title = title if title else "Unknown Title"
    final_abstract = abstract if abstract else "Abstract not available in open databases."
    return final_title, clean_abstract(final_abstract)

# --- Streamlit UI Setup ---
st.set_page_config(page_title="SLR Metadata Fetcher", layout="wide")
st.title("📚 SLR Metadata Fetcher")
st.markdown(
    "Upload your team's `.bib` file. The app will extract the DOIs, query **Crossref**, "
    "and automatically fall back to **Semantic Scholar** if the abstract is missing."
)

uploaded_file = st.file_uploader("Upload .bib file", type=["bib"])

if uploaded_file is not None:
    st.info("Parsing BibTeX file... Please wait.")
    
    # Parse the bib file contents
    bib_string = uploaded_file.getvalue().decode("utf-8")
    bib_database = bibtexparser.loads(bib_string)
    entries = bib_database.entries
    
    st.success(f"Found {len(entries)} total entries in the file.")
    
    # Convert to DataFrame to find DOI column safely
    df = pd.DataFrame(entries)
    
    if 'doi' not in df.columns:
        st.error("No 'doi' field found in this BibTeX file. Please ensure your ACM/IEEE export includes DOIs.")
    else:
        # Clean up DOIs (remove common URL prefixes if present)
        df['clean_doi'] = df['doi'].dropna().apply(
            lambda x: str(x).replace('https://doi.org/', '').replace('http://doi.org/', '').strip()
        )
        doi_list = df['clean_doi'].dropna().tolist()
        
        st.metric(label="Valid DOIs Found", value=len(doi_list))
        
        # UI controls for batching
        process_limit = st.slider(
            "Select number of papers to fetch (Batching recommended to avoid API limits)", 
            1, len(doi_list), min(100, len(doi_list))
        )
        
        # Dynamic sleep time adjustment based on tier/rate limiting
        sleep_time = st.number_input(
            "Delay between requests (seconds). Increase if hitting rate limits.", 
            min_value=0.5, max_value=5.0, value=1.5, step=0.5
        )
        
        if st.button("🚀 Fetch Titles & Abstracts"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            results = []
            
            for i, doi in enumerate(doi_list[:process_limit]):
                status_text.text(f"Processing {i+1}/{process_limit} | Fetching DOI: {doi}...")
                
                title, abstract = fetch_metadata_dual_engine(doi)
                results.append({
                    "BibTeX Index": i + 1,
                    "DOI": doi,
                    "Fetched Title": title,
                    "Fetched Abstract": abstract
                })
                
                # Update progress bar
                progress_bar.progress((i + 1) / process_limit)
                time.sleep(sleep_time) 
                
            status_text.text("✅ Fetching sequence complete!")
            
            # Display results in UI
            results_df = pd.DataFrame(results)
            st.subheader("Fetched Data Preview")
            st.dataframe(results_df, use_container_width=True)
            
            # Download Action
            csv = results_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Results as CSV",
                data=csv,
                file_name='slr_fetched_abstracts.csv',
                mime='text/csv',
            )
