import sys
import json
import httplib
import urllib
import libsvm_formatter

from optparse import OptionParser
from multiprocessing import Pool

solrQueryUrl = ""


def setupSolr(collection, host, port, featuresFile, featureStoreName):
    '''Sets up solr with the proper features for the test'''

    print "...Setting up connection with %s port %s" % (host, port)

    conn = httplib.HTTPConnection(host, port)

    baseUrl = "/solr/" + collection
    featureUrl = baseUrl + "/schema/feature-store"

    print "...Deleting old feature set: %s/%s" % (featureUrl, featureStoreName)
    conn.request("DELETE", featureUrl+"/"+featureStoreName)

    r = conn.getresponse()
    msg = r.read()
    if (r.status != httplib.OK and
        r.status != httplib.CREATED and
        r.status != httplib.ACCEPTED and
        r.status != httplib.NOT_FOUND):
        raise Exception("Status: {0} {1}\nResponse: {2}".format(r.status, r.reason, msg))

    print "...Adding new feature set..."

    # Add features
    headers = {'Content-type': 'application/json'}
    featuresBody = open(featuresFile)

    conn.request("POST", featureUrl, featuresBody, headers)
    r = conn.getresponse()
    msg = r.read()
    if (r.status != httplib.OK and
        r.status != httplib.ACCEPTED):
        print r.status
        print ""
        print r.reason;
        raise Exception("Status: {0} {1}\nResponse: {2}".format(r.status, r.reason, msg))

    conn.close()
    print "...New feature set successfully uploaded..."


def generateQueries(userQueriesFile, collection, requestHandler, solrFeatureStoreName, efiParams, host, port):

    solrQueryUrls = [] # A list of tuples with solrQueryUrl,solrQuery,docId,scoreForPQ,source
    with open(userQueriesFile) as input:

        for line in input:
            line = line.strip();
            searchText,docId,score,source = line.split("|");
            solrQuery = generateHttpRequest(collection,requestHandler,solrFeatureStoreName,efiParams,searchText,docId)
            solrQueryUrls.append((solrQuery,searchText,docId,score,source,host,port))

    return solrQueryUrls


def generateHttpRequest(collection, requestHandler, solrFeatureStoreName, efiParams, searchText, docId):
    global solrQueryUrl
    if len(solrQueryUrl) < 1:
        solrQueryUrl = "/".join([ "", "solr", collection, requestHandler ])
        solrQueryUrl += ("?fl=" + ",".join([ "Id", "score", "[features store="+solrFeatureStoreName+" "+efiParams+"]" ]))
        solrQueryUrl += "&q="
        solrQueryUrl = solrQueryUrl.replace(" ","+")
        solrQueryUrl += urllib.quote_plus("Id:")


    userQuery = urllib.quote_plus(searchText.strip().replace("'","\\'").replace("/","\\\\/"))
    userQueryComma = urllib.quote_plus(searchText.strip().replace("'","\\'").replace("/","\\\\/").replace(" ",","))

    solrQuery = solrQueryUrl + '"' + urllib.quote_plus(docId) + '"' #+ solrQueryUrlEnd
    solrQuery = solrQuery.replace('$USERQUERY', urllib.quote("\\'" + userQuery + "\\'"))
    solrQuery = solrQuery.replace('$QUERYCOMMA', userQueryComma)

    return solrQuery


def generateTrainingData(solrQuery):
    '''Given a list of solr queries, yields a tuple of query , docId , score , source , feature vector for each query.
    Feature Vector is a list of strings of form "key=value"'''


    queryUrl,query,docId,score,source, host, port = solrQuery

    conn = httplib.HTTPConnection(host, port)
    headers = {"Connection":" keep-alive"}

    try:
        conn.request("GET", queryUrl, headers=headers)
        r = conn.getresponse()
        msg = r.read()
        msgDict = json.loads(msg)
        fv = ""
        docs = msgDict['response']['docs']
        if len(docs) > 0 and "[features]" in docs[0]:
            if not msgDict['response']['docs'][0]["[features]"] == None:
                fv = msgDict['response']['docs'][0]["[features]"];
            else:
                print "ERROR NULL FV FOR: " + docId;
                print msg
                return ()
        else:
            print "ERROR FOR: " + docId;
            print msg
            print >> sys.stderr, docId
            return ()

        if r.status == httplib.OK:
            print "...http connection was ok for: " + queryUrl
            conn.close()
            return (query,docId,score,source,fv.split(","))
        else:
            raise Exception("Status: {0} {1}\nResponse: {2}".format(r.status, r.reason, msg))
            return ()

    except Exception as e:
        print msg
        print e
        return ()

def uploadModel(collection, host, port, modelFile, modelName):
    modelUrl = "/solr/" + collection + "/schema/model-store"
    headers = {'Content-type': 'application/json'}
    with open(modelFile) as modelBody:
        conn = httplib.HTTPConnection(host, port)

        conn.request("DELETE", modelUrl+"/"+modelName)
        r = conn.getresponse()
        msg = r.read()
        if (r.status != httplib.OK and
            r.status != httplib.CREATED and
            r.status != httplib.ACCEPTED and
            r.status != httplib.NOT_FOUND):
            raise Exception("Status: {0} {1}\nResponse: {2}".format(r.status, r.reason, msg))

        conn.request("POST", modelUrl, modelBody, headers)
        r = conn.getresponse()
        msg = r.read()
        if (r.status != httplib.OK and
            r.status != httplib.CREATED and
            r.status != httplib.ACCEPTED):
                raise Exception("Status: {0} {1}\nResponse: {2}".format(r.status, r.reason, msg))


def main(argv=None):
    if argv is None:
        argv = sys.argv

    parser = OptionParser(usage="usage: %prog [options] ", version="%prog 1.0")
    parser.add_option('-c', '--config',
                      dest='configFile',
                      help='File of configuration for the test')
    (options, args) = parser.parse_args()

    if options.configFile == None:
        parser.print_help()
        return 1

    with open(options.configFile) as configFile:
        config = json.load(configFile)

        print "Uploading features ("+config["solrFeaturesFile"]+") to Solr"
        setupSolr(config["collection"], config["host"], config["port"], config["solrFeaturesFile"], config["solrFeatureStoreName"])

        print "Converting user queries ("+config["userQueriesFile"]+") into Solr queries for feature extraction"
        reRankQueries = generateQueries(config["userQueriesFile"], config["collection"], config["requestHandler"], config["solrFeatureStoreName"], config["efiParams"], config["host"], config["port"])

        print "Running Solr queries to extract features"

        pool = Pool(processes=None)
        fvGenerator = pool.map(generateTrainingData, reRankQueries)
        #fvGenerator = generateTrainingData(reRankQueries)

        fvGenerator = [t for t in fvGenerator if t and len(t) > 0]

        #print list(fvGenerator)
        formatter = libsvm_formatter.LibSvmFormatter()
        formatter.processQueryDocFeatureVector(fvGenerator,config["trainingFile"])

        print "Training model using '"+config["trainingLibraryLocation"]+" "+config["trainingLibraryOptions"]+"'"
        print "Training file: %s and output model %s" % (config["trainingFile"], config["trainedModelFile"])

        libsvm_formatter.trainLibSvm(config["trainingLibraryLocation"],config["trainingLibraryOptions"],config["trainingFile"],config["trainedModelFile"])
        """
        print "TRYING"
        from subprocess import call
        call([config["trainingLibraryLocation"],config["trainingFile"],config["trainedModelFile"]])
        print [config["trainingLibraryLocation"],config["trainingLibraryOptions"],config["trainingFile"],config["trainedModelFile"]]
        print "DONE"
        """

        print "Converting trained model ("+config["trainedModelFile"]+") to solr model ("+config["solrModelFile"]+")"
        formatter.convertLibSvmModelToLtrModel(config["trainedModelFile"], config["solrModelFile"], config["solrModelName"], config["solrFeatureStoreName"])

        print "Uploading model ("+config["solrModelFile"]+") to Solr"
        uploadModel(config["collection"], config["host"], config["port"], config["solrModelFile"], config["solrModelName"])

if __name__ == '__main__':
    sys.exit(main())


