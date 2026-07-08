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

def fetch_crossref_metadata(doi):
    """Fetches title and abstract from Crossref API using DOI."""
    # It is highly recommended to use the 'polite pool' by adding your email
    headers = {"User-Agent": "SLR_Metadata_Fetcher/1.0 (mailto:your_email@example.com)"}
    url = f"https://api.crossref.org/works/{doi}"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()['message']
            title = data.get('title', [''])[0]
            abstract = data.get('abstract', '')
            return title, clean_abstract(abstract)
        else:
            return None, f"Error: API returned status {response.status_code}"
    except Exception as e:
        return None, f"Request failed: {e}"

# --- UI Setup ---
st.set_page_config(page_title="SLR Metadata Fetcher", layout="wide")
st.title("📚 SLR Metadata Fetcher")
st.markdown("Upload your `.bib` file. The app will extract DOIs and fetch titles/abstracts via Crossref.")

uploaded_file = st.file_uploader("Upload .bib file", type=["bib"])

if uploaded_file is not None:
    st.info("Parsing BibTeX file...")
    # Parse the bib file
    bib_string = uploaded_file.getvalue().decode("utf-8")
    bib_database = bibtexparser.loads(bib_string)
    
    entries = bib_database.entries
    st.success(f"Found {len(entries)} entries in the file.")
    
    # Extract entries with DOIs
    df = pd.DataFrame(entries)
    if 'doi' not in df.columns:
        st.error("No DOIs found in this BibTeX file. DOIs are required to fetch metadata.")
    else:
        # Clean DOIs (sometimes they have URLs attached)
        df['clean_doi'] = df['doi'].dropna().apply(lambda x: x.replace('https://doi.org/', '').strip())
        doi_list = df['clean_doi'].dropna().tolist()
        
        st.write(f"**{len(doi_list)}** entries have valid DOIs ready for processing.")
        
        # Select how many to process (to avoid API rate limits during testing)
        process_limit = st.slider("Select number of papers to fetch (batching is recommended)", 1, len(doi_list), min(100, len(doi_list)))
        
        if st.button("Fetch Titles & Abstracts"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            results = []
            
            for i, doi in enumerate(doi_list[:process_limit]):
                status_text.text(f"Fetching {i+1}/{process_limit}: {doi}...")
                
                title, abstract = fetch_crossref_metadata(doi)
                results.append({
                    "DOI": doi,
                    "Fetched Title": title,
                    "Fetched Abstract": abstract
                })
                
                # Polite delay to avoid getting blocked by Crossref (Rate limit is usually 50 requests/second, but safe is better)
                time.sleep(0.2) 
                progress_bar.progress((i + 1) / process_limit)
                
            status_text.text("Fetching complete!")
            
            # Display Results
            results_df = pd.DataFrame(results)
            st.dataframe(results_df)
            
            # Download Button
            csv = results_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Results as CSV",
                data=csv,
                file_name='slr_abstracts.csv',
                mime='text/csv',
            )
