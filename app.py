
import streamlit as st
import requests
import pandas as pd
import unicodedata
import re
from urllib.parse import quote
from io import BytesIO

YEARS = list(range(2014, 2025))

def clean_text(text):
    if text is None:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace('\xa0', ' ')
    text = re.sub(r'[^\x00-\x7F]+', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def search_journals(journal_name):
    encoded_name = quote(journal_name)
    url = f"https://api.openalex.org/sources?search={encoded_name}&per-page=5"
    response = requests.get(url)
    if response.status_code != 200:
        return []
    return response.json().get("results", [])

def get_articles(journal_id, year):
    articles = []
    cursor = "*"
    while True:
        url = (
            f"https://api.openalex.org/works?"
            f"filter=locations.source.id:{quote(journal_id)},from_publication_date:{year}-01-01,"
            f"to_publication_date:{year}-12-31&per-page=200&cursor={cursor}"
        )
        response = requests.get(url)
        if response.status_code != 200:
            break

        data = response.json()
        articles.extend(data.get("results", []))

        meta = data.get("meta", {})
        if meta.get("next_cursor"):
            cursor = meta["next_cursor"]
        else:
            break

    return articles

def get_citations_by_year(article):
    citation_counts = {str(year): 0 for year in YEARS}
    for entry in article.get("counts_by_year", []):
        year = str(entry.get("year"))
        if year in citation_counts:
            citation_counts[year] = entry.get("cited_by_count", 0)
    return citation_counts

def build_excel(journal_name, year):
    matches = search_journals(journal_name)
    if not matches:
        return None, "No journal matches found."

    selected = matches[0]
    journal_id = selected["id"]
    journal_name = selected["display_name"]

    articles = get_articles(journal_id, year)
    if not articles:
        return None, "No articles found for that journal/year."

    data = []
    for article in articles:
        title = article.get("title", "")
        biblio = article.get("biblio", {})
        issue = biblio.get("issue", "Unknown")
        month = biblio.get("month")
        pub_date = article.get("publication_date", "")

        if not month:
            if len(pub_date) >= 7:
                month = pub_date[5:7]
            else:
                month = "Unknown"

        citation_counts = get_citations_by_year(article)
        row = {
            "Title": clean_text(title),
            "Journal Name": journal_name,
            "Issue": issue,
            "Month": month,
            "Publication Date": pub_date
        }
        for y in YEARS:
            row[str(y)] = citation_counts.get(str(y), 0)
        data.append(row)

    df = pd.DataFrame(data)
    df.sort_values(by='Publication Date', inplace=True)
    buffer = BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)
    return buffer, None

st.title("OpenAlex Journal Article Scraper")

journal_name = st.text_input("Enter journal name")
year = st.number_input("Enter year", min_value=1900, max_value=2100, step=1)

if st.button("Get Articles"):
    if journal_name and year:
        excel_data, error = build_excel(journal_name, int(year))
        if error:
            st.error(error)
        else:
            st.success("Done! Download your file below:")
            st.download_button(
                label="📥 Download Excel",
                data=excel_data,
                file_name=f"journal_articles_{year}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.warning("Please enter both journal name and year.")
