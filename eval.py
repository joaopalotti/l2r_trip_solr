import sys
import json
from optparse import OptionParser

import httplib
import urllib
import numpy as np
import random

def issueQuery(searchText, host, port, collection, requestHandler,
            solrFeatureStoreName, efiParams, rerank, ltr_model, likeInTrip=True):

    conn = httplib.HTTPConnection(host, port)
    headers = {"Connection":" keep-alive"}
    solrQueryUrl = "/".join([ "", "solr", collection, requestHandler ])
    #solrQueryUrl += ("?fl=" + ",".join([ "Id", "score", "Title", "TitleAndBody", "Url", "SortDate", "[features store="+solrFeatureStoreName+" "+efiParams+"]" ]))
    solrQueryUrl += ("?fl=" + ",".join([ "Id", "score", "[features store="+solrFeatureStoreName+" "+efiParams+"]" ]))

    if likeInTrip:
        # Include boost by Weight and search made only in the titleNoSyn:
        searchTextInTitle = "+".join(["TitleNoSyn:%s" % (t) for t in searchText.split(" ")])
        solrQueryUrl += " ".join(["&q={!boost b=Weight}",searchTextInTitle])

        # add field filter to query
        titleAndBodyFilter = "+AND+".join(["TitleAndBody:%s" % (t) for t in searchText.split(" ")])
        solrQueryUrl += " ".join(["&fq=" + titleAndBodyFilter])

        # add category filter to query
        catFilter = "Category:(11 OR 1 OR 16 OR 18 OR 10 OR 9 OR 4 OR 2 OR 13 OR 14 OR 5 OR 27 OR 22 OR 29)"
        solrQueryUrl += " ".join(["&fq=" + catFilter])

    else:
        # Plain search
        solrQueryUrl += " ".join(["&q=",searchText])

    userQuery = urllib.quote_plus(searchText.strip().replace("'","\\'").replace("/","\\\\/"))
    userQueryComma = urllib.quote_plus(searchText.strip().replace("'","\\'").replace("/","\\\\/").replace(" ",","))

    if rerank is not None:
        #rq={!ltr%20model=exampleModel%20efi.user_query=lung%20cancer%20efi.user_query_comma=lung,cancer}
        solrQueryUrl += " ".join(["&rq=","{!ltr+model=", ltr_model])
        if rerank > 0:
            solrQueryUrl += "".join([" ","reRankDocs=", str(rerank)])
        solrQueryUrl += " ".join(["", efiParams, "}"])

    solrQuery = solrQueryUrl.replace(" ","+")
    solrQuery = solrQuery.replace('$USERQUERY', urllib.quote("\\'" + userQuery + "\\'"))
    solrQuery = solrQuery.replace('$QUERYCOMMA', userQueryComma)

    #print "Final Query: %s" % (solrQuery)
    docs = []
    try:
        #print "Querying: ", solrQuery
        conn.request("GET", solrQuery, headers=headers)
        r = conn.getresponse()
        msg = r.read()
        msgDict = json.loads(msg)
        docs = msgDict['response']['docs']

    except Exception as e:
        print e
    conn.close()
    return docs

def save_avg_prec(docs_rerank, docids, option, avg_prec):
    avg = []
    rel_so_far = 0.0

    for i in range(len(docs_rerank)):
        d = docs_rerank[i]
        if d["Id"] in docids:
            rel_so_far += 1
            avg.append( rel_so_far / (i+1) )

    if len(avg) == 0:
        avg.append(0.0)

    avg_prec[option].append(np.mean(avg))

if __name__ == "__main__":

    argv = sys.argv

    parser = OptionParser(usage="usage: %prog [options] ", version="%prog 1.0")
    parser.add_option('-c', '--config',
                      dest='configFile',
                      help='File of configuration for the test')
    parser.add_option('-f', '--file',
                      dest='queryFile',
                      help='File with a list of <query>|<docid>')
    parser.add_option('-r', '--rerank',
                      dest='rerankN',
                      help='Number of documents to be part of the rererank set')
    parser.add_option('-n', '--nqueries',
                      dest='nqueries',
                      default = "1000",
                      help='Number of queries to run (default=1000)')

    (options, args) = parser.parse_args()

    if options.configFile == None or options.queryFile == None or options.rerankN == None:
        parser.print_help()
        sys.exit(1)

    with open(options.configFile) as configFile:
        config = json.load(configFile)

    with open(options.queryFile) as queryFile:
        queries = [line.split("|") for line in queryFile.readlines()]

    avg_prec = {"normal" : [], "rerank": []}

    random.seed(1)
    qs = []
    for i in range(int(options.nqueries)):
        qs.append(random.choice(queries))

    print "Running %d queries..." % (len(qs))
    for i, (query, docids) in enumerate(qs):
        docids = docids.strip().split(",")

        docs_rerank = issueQuery(query, config["host"], config["port"], config["collection"],
                          config["requestHandler"], config["solrFeatureStoreName"],
                          config["efiParams"], options.rerankN, config["solrModelName"], True)

        docs_normal = issueQuery(query, config["host"], config["port"], config["collection"],
                          config["requestHandler"], config["solrFeatureStoreName"],
                          config["efiParams"], None, config["solrModelName"], True)

        save_avg_prec(docs_rerank, docids, "rerank", avg_prec)
        save_avg_prec(docs_normal, docids, "normal", avg_prec)

        progress = 100. * i / len(qs)
        sys.stdout.write("Current Progress: %.2f%%   \r" % (progress) )
        sys.stdout.flush()

    print "MAP for normal Trip: %.3f - std %.4f" % (np.mean(avg_prec["normal"]), np.std(avg_prec["normal"]))
    print "MAP for reranked Trip: %.3f - std %.4f" % (np.mean(avg_prec["rerank"]), np.std(avg_prec["rerank"]) )
    print "Improvement: %.2f%%" % ( 100. * ((np.mean(avg_prec["rerank"]) / np.mean(avg_prec["normal"]))- 1.0))

