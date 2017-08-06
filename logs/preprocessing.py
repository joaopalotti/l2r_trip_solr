import pandas as pd
import numpy as np
import json
import re

def removeEmptyKeywords(df):
    # Remove the set queries with no keywords:
    return df[df["Keywords"].apply(lambda x : True if len(x)>0 else False)]

def removeEmptyDocLists(df):
    # Remove queries that had no Document list
    return df[df["Documents"].apply(lambda x : True if x and len(x)>0 else False)]

def transformData(df, field="DateCreated"):
    "From Date(xxxxxxxxxxxx), we are interested in the first 11 digits from the left hand side"
    return pd.to_datetime(df[field].apply(lambda x: x[6:-5]), unit='s')

def preprocessKeywords(df):
    " Tokenizes and clean keywords"

    # Cleaning keywords
    pattern = re.compile('[\W_]+')

    df["Keywords"] = df["Keywords"].apply(lambda x: re.sub("title:","",x))
    df["Keywords"] = df["Keywords"].apply(lambda x: re.sub("from:[\d]+", "", x))
    df["Keywords"] = df["Keywords"].apply(lambda x: re.sub("to:[\d]+", "", x))
    df["Keywords"] = df["Keywords"].apply(lambda x: re.sub('area:"[\w ]+"', "", x))

    # KeywordsSet is a tuple of keywords used in a query
    df["KeywordsSet"] = df["Keywords"].apply(lambda x : tuple(sorted(set([w for w in pattern.sub(' ',x.lower()).strip().split() if w]))))

    # Remove the set queries with no keywords:
    return df[df["KeywordsSet"].apply(lambda x : True if len(x)>0 else False)]

def __getDocScores(serps):
    docs = {}
    for serp in serps:
        docs_scores = json.loads(serp)
        for doc_score in docs_scores:
            doc, score = doc_score.strip().split(":")
            docs[doc] = float(score)
    return docs

def assignQueryIds(df):
    """
    Assign a number to each group
    """
    tmp_counter = []
    i = 0
    for (sessionid, keywords), _ in df[["SessionId","Keywords"]].groupby(["SessionId","Keywords"]):
        tmp_counter.append([sessionid, keywords, i])
        i += 1
    queryId = pd.DataFrame(tmp_counter, columns=["SessionId", "Keywords", "QueryId"])
    return pd.merge(df, queryId, on = ["SessionId", "Keywords"])

def getDocScores(df):
    # This grouping procedure is too slow:
    # X = df[["SessionId", "KeywordsSet","Documents"]].groupby(["SessionId", "KeywordsSet"])["Documents"].apply(getDocScores)
    # Replaced by:
    tmp_mapping = []
    for queryid, group in df[["QueryId","Documents"]].groupby(["QueryId"])["Documents"]:
        for doc, value in __getDocScores(group).iteritems():
            tmp_mapping.append([queryid, int(doc), float(value)])
    X = pd.DataFrame(tmp_mapping, columns=["QueryId", "DocumentId","Score"])
    # Done.
    return X

def getDocRelevance(df):
    #query_doc_rel = df[["QueryId", "DocumentId"]].groupby(["QueryId")["DocumentId"].apply(lambda x : list(x))
    tmp_mapping = []
    for queryid, group in df[["QueryId","DocumentId"]].groupby(["QueryId"])["DocumentId"]:
        for doc in group:
            tmp_mapping.append([queryid, doc])
    y = pd.DataFrame(tmp_mapping, columns=["QueryId", "DocumentId"])
    y["Relevant"] = True
    # Done.
    return y

def generateLetor(docScores, relevance, popularityDocId, charsInQuery, keywordsInQuery, popularityPairKeywordDocId, normalize=True):
    # Merge left is used to have all the query, document combinations in the new dataset letor:
    letor = pd.merge(docScores, relevance, on=["QueryId", "DocumentId"], how="left")
    letor["Relevant"].fillna(False, inplace=True)

    letor = pd.merge(letor, popularityDocId, on="DocumentId", how="left")
    letor["PopularityDocId"] = letor["PopularityDocId"].fillna(0.0)

    letor = pd.merge(letor, popularityPairKeywordDocId, on=["DocumentId","QueryId"], how="left")
    letor["PopularityKeywordDocId"] = letor["PopularityKeywordDocId"].fillna(0.0)

    letor = pd.merge(letor, charsInQuery)

    letor = pd.merge(letor, keywordsInQuery)

    if normalize:
        keys_to_normalize = ["Score","PopularityDocId","PopularityKeywordDocId","CharsInQuery","KeywordsInQuery"]
        letor[keys_to_normalize] = letor[keys_to_normalize].apply(lambda x: (x - np.mean(x)) / (np.max(x) - np.min(x)))

    return letor

#######
#######
####### Methods to create features
#######
#######

def createFeatureCharsInQuery(df):
    """
    Generate a simple feature for the number of chars in a query.
    File created features/charQuery.pickle with <DocId,Int>.
    """
    charPerQuery = df[["QueryId","Keywords"]].drop_duplicates().set_index("QueryId")["Keywords"].apply(len).reset_index()
    charPerQuery.rename(columns={"Keywords":"CharsInQuery"}, inplace=True)
    charPerQuery.to_pickle("features/charsInQuery.pickle")

def createFeatureKeywordsInQuery(df):
    """
    Generate a simple feature counting the number of keywords in a query.
    File created features/keywordsInQuery.pickle with <DocId,Int>.
    """
    keywordsInQuery = df[["QueryId","KeywordsSet"]].drop_duplicates().set_index("QueryId")["KeywordsSet"].apply(len).reset_index()
    keywordsInQuery.rename(columns={"KeywordsSet":"KeywordsInQuery"}, inplace=True)
    keywordsInQuery.to_pickle("features/keywordsInQuery.pickle")

def createFeaturePopularityKeywordDocId(df):
    """
    Generate a simple feature counting how may times the pair <keyword, doc> was clicked.
    File created features/popularityKeywordDocId.pickle with <KeywordSet,DocId,Int>.
    """
    df["Popularity"] = 1
    keywordsDocPop = df[["KeywordsSet","DocumentId","Popularity"]].groupby(["KeywordsSet","DocumentId"]).count().reset_index()
    keywordsDocPop.rename(columns={"Popularity":"PopularityKeywordDocId"}, inplace=True)
    del df["Popularity"]

    keywordsDocPop = pd.merge(df[["QueryId","KeywordsSet","DocumentId"]], keywordsDocPop, on=["KeywordsSet","DocumentId"], how="left")
    keywordsDocPop.to_pickle("features/popularityKeywordDocId.pickle")

def createFeatureDocPopularity(df):
    """
    Counts how many times a document has been clicked.
    """
    df["Popularity"] = 1
    docPop = df[["DocumentId", "Popularity"]].groupby(["DocumentId"])["Popularity"].sum().reset_index()
    docPop.rename(columns={"Popularity":"PopularityDocId"}, inplace=True)
    del df["Popularity"]
    docPop.to_pickle("features/popularityDocId.pickle")

#######
#######
####### Methods to obtain features
#######
#######

def getFeatureKeywordsInQuery():
    return pd.read_pickle("features/keywordsInQuery.pickle")

def getFeatureCharsInQuery():
    return pd.read_pickle("features/charsInQuery.pickle")

def getFeatureDocPopularity():
    return pd.read_pickle("features/popularityDocId.pickle")

def getFeaturePopularityKeywordDocId():
    return pd.read_pickle("features/popularityKeywordDocId.pickle")

#######
#######
#######
#######
#######
def printLetor(letor, printDocNames=False):
    """
    Print dataframe in format for L2T softwares

    2 qid:10032 1:0.056537 2:0.000000 3:0.666667 4:1.000000 5:0.067138 ... 45:0.000000 46:0.076923
    0 qid:10032 1:0.279152 2:0.000000 3:0.000000 4:0.000000 5:0.279152 ... 45:0.250000 46:1.000000
    0 qid:10032 1:0.130742 2:0.000000 3:0.333333 4:0.000000 5:0.134276 ... 45:0.750000 46:1.000000
    """
    if printDocNames:
        outfile = open("docnames.txt", "w")

    letor = letor.sort_values(by=["QueryId"])
    for (index, series) in letor.iterrows():
        print "%d qid:%d"  % (series["Relevant"], series["QueryId"]),
        print "1:%.3f" % (series["Score"]),
        print "2:%.3f" % (series["PopularityDocId"]),
        print "3:%.3f" % (series["PopularityKeywordDocId"]),
        print "4:%.3f" % (series["CharsInQuery"]),
        print "5:%.3f" % (series["KeywordsInQuery"]),
        print "# DocId: %s, QId: %s" % (series["DocumentId"], series["QueryId"])

        if printDocNames:
            outfile.write("%s\n" % series["DocumentId"])

