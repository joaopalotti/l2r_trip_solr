import pandas as pd
import numpy as np
import sys
import re
from preprocessing import *

"""
Run load_logs.py first.
I am only using the logs from /bigdata/palotti/trip/ltr/logs

"""
input_file = sys.argv[1]

# Loads pickle created by load_logs.py
#df = pd.read_pickle("df.pickle")
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

groupSets = df[["Documents", "SessionId", "Position", "KeywordsSet", "DateCreated", "DocumentId"]].groupby(["SessionId", "KeywordsSet"])
#clickedDocs = groupSets["DocumentId"].apply(set)

"""
Implementing and adptation of Last Click > Skip Above from Joachims SIGIR'05
Here I am considering relevant the last click in the session and considering non relevant the skiped documents.
"""

for group in groupSets:
    name, rows = group
    query = ' '.join(name[1])

    nqueries = len(rows)

    documents = {}
    clickedDocuments = set([])

    lastDocClicked = None
    lastPos = None

    for idx, row in rows.iterrows():
        clicked = row["DocumentId"]
        clickedDocuments.add(clicked)
        # recods pos and docid for the last clicked document
        lastDocClicked = clicked
        lastPos = int(row["Position"])

    serp = extract_docs_from_serp(row["Documents"])

    for i in range(min(lastPos,len(serp))):
        docid = serp[i]
        if int(docid) not in clickedDocuments:
            documents[docid] = 0.0

    documents[lastDocClicked] = 1.0

    # Skip if we just have one single clicked document
    if len(documents) == 1:
        continue

    for docid, relevance in documents.items():
        print("%s|%s|%.2f|CLICKLOGS" % (query, docid, relevance))

