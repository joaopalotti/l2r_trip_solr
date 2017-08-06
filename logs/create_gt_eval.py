import pandas as pd
import numpy as np
import sys
import re
from preprocessing import *

"""
Given a df.pickle with all query logs, it outputs the query and the last document clicked
"""
input_file = sys.argv[1]

# Loads pickle created by load_logs.py
df = pd.read_pickle(input_file)

# Preprocessing steps:
df = removeEmptyKeywords(df)
df = removeEmptyDocLists(df)
df = preprocessKeywords(df)
df = assignQueryIds(df)

df["DateCreated"] = transformData(df)

def extract_docs_from_serp(serp):
    docs = []
    docs_scores = json.loads(serp)
    for doc_score in docs_scores:
        doc, score = doc_score.strip().split(":")
        docs.append(doc)
    return docs

df = df.sort_values(["SessionId","DateCreated"]).reset_index(drop=True)
groupSets = df[["Documents", "SessionId", "Position", "KeywordsSet", "DateCreated", "DocumentId"]].groupby(["SessionId", "KeywordsSet"])

"""
Here I am considering relevant ONLY the last click in the session.
"""

for group in groupSets:
    name, rows = group
    query = ' '.join(name[1])

    lastDocClicked = None

    for idx, row in rows.iterrows():
        clicked = row["DocumentId"]
        # recods pos and docid for the last clicked document
        lastDocClicked = clicked

    print("%s|%s" % (query, lastDocClicked))

