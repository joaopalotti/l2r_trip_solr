import pandas as pd
import json
import sys
from preprocessing import removeEmptyKeywords, removeEmptyDocLists, preprocessKeywords
from preprocessing import assignQueryIds, transformData

"""
Given a df.pickle with all query logs, it outputs the query and the last document clicked
"""

if len(sys.argv) != 3:
    print "Parameters are not correctly set"
    print "python create_gt_eval.py input_file=df.pickle strategy=[all|first|last]"
    sys.exit(0)

input_file = sys.argv[1]
strategy = sys.argv[2]

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
groupSets = df.head(10)[["Documents", "SessionId", "Position", "KeywordsSet", "DateCreated", "DocumentId"]].groupby(["SessionId", "KeywordsSet"])

"""
Here I am considering relevant ONLY the last click in the session.
"""

for group in groupSets:
    name, rows = group
    query = ' '.join(name[1])

    docs = []
    if strategy == "last":
        for idx, row in rows.iterrows():
            clicked = row["DocumentId"]
        docs = [clicked]

    elif strategy == "first":
        for idx, row in rows.iterrows():
            clicked = row["DocumentId"]
            docs = [clicked]
            break

    elif strategy == "all":
        for idx, row in rows.iterrows():
            clicked = row["DocumentId"]
            docs.append(clicked)

    print("%s|%s" % (query, ",".join(map(str,docs))))

