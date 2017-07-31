import web
import json
import httplib
import urllib
import copy
from web import form

render = web.template.render('templates/')

urls = (
    '/', 'Index',
    '/query', 'query',
    '/features', 'features',
)

def connectQuery(searchText, host="solr65.tripdatabase.com", port="80", collection="trip", requestHandler="query",
            solrFeatureStoreName="TripFeatures", efiParams="efi.user_query=$USERQUERY efi.user_query_comma=$QUERYCOMMA",
            rerank=None, ltr_model="tripModel", likeInTrip=True):

    conn = httplib.HTTPConnection(host, port)
    headers = {"Connection":" keep-alive"}
    solrQueryUrl = "/".join([ "", "solr", collection, requestHandler ])
    solrQueryUrl += ("?fl=" + ",".join([ "Id", "score", "Title", "TitleAndBody", "Url", "SortDate", "[features store="+solrFeatureStoreName+" "+efiParams+"]" ]))

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

    print "Final Query: %s" % (solrQuery)
    docs = []
    try:
        #print "Querying: ", solrQuery
        conn.request("GET", solrQuery, headers=headers)
        r = conn.getresponse()
        msg = r.read()
        msgDict = json.loads(msg)
        docs = msgDict['response']['docs']

    except Exception as e:
        print msg
        print e
    conn.close()
    return docs

class Index:
    def GET(self):
        return render.index()

class Doc:
    def __init__(self, id, title, url, titleAndBody, date=""):
        self.id = id
        self.title = title
        self.url = url
        self.date = date
        self.titleAndBody = titleAndBody

def transformObject(docs):
    return [ Doc(d['Id'],d['Title'],d['Url'],d['TitleAndBody'],d['SortDate']) for d in docs ]

queryform = form.Form(
    form.Textbox("Query", form.notnull, id="query"),
    form.Dropdown("N", args=['All','3','5','10','20','50','100','500','1000','10000'], value='5', id="N", description="Number of documents to rerank:")
)

class query:

    def GET(self):
        f = queryform()
        return render.query(f)

    def POST(self):
        f = queryform()
        if not f.validates():
            return render.query(f)

        searchText = f['Query'].value
        n = 0 if f["N"].value == "All" else int(f["N"].value)
        print "Running query with: ", searchText, "reranking ",n
        docs = transformObject(connectQuery(searchText))
        docs_reranked = transformObject(connectQuery(searchText, rerank=n))

        return render.query(f, docs, docs_reranked)

with open("tripModel.json", "r") as f:
    model = json.load(f)

def createFeatureForm(model):

    featureComponents = []
    for f in sorted(model["features"]):
        featureComponents.append(form.Textbox(f["name"], form.notnull, id=f["name"], value="%.8f" % model["params"]["weights"][f["name"]]))
    featureComponents.append(form.Button(name="save", type="submit", html="Save Changes & Upload New Model"))
    featureComponents.append(form.Button(name="restore", type="submit", html="Restore Default Model"))
    featureComponents.append(form.Button(name="download", type="submit", html="Download Current Model"))
    featuresform = form.Form(*featureComponents)
    return featuresform

featuresform = createFeatureForm(model)

def upload(modelContent, collection="trip", host="solr65.tripdatabase.com", port="80", modelName="tripModel"):

    modelFile = "newmodel.json"
    with open(modelFile, "w") as f:
        json.dump(modelContent, f, indent=4)

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
            raise Exception("Deleting Error: {0} {1}\nResponse: {2}".format(r.status, r.reason, msg))
        print "Deleted old model with success"

        conn.request("POST", modelUrl, modelBody, headers)
        r = conn.getresponse()
        msg = r.read()
        if (r.status != httplib.OK and
            r.status != httplib.CREATED and
            r.status != httplib.ACCEPTED):
                raise Exception("Upload Error: {0} {1}\nResponse: {2}".format(r.status, r.reason, msg))

def saveState(f):
    newmodel = copy.deepcopy(model)
    for feat in sorted(newmodel["features"]):
        newmodel["params"]["weights"][feat["name"]] = float(f[feat["name"]].value)
    return newmodel

class features:

    def GET(self):
        f = featuresform()
        return render.features(f, "")

    def POST(self):
        f = featuresform()
        if not f.validates():
            return render.features(f, "")

        if f["save"].value is not None:
            print("Clicked on SAVE button")

            newmodel = saveState(f)
            print newmodel["params"]["weights"]["BoostWeightScore"]
            print model["params"]["weights"]["BoostWeightScore"]

            upload(newmodel)
            message = "New model saved and uploaded! Have Fun!"

        elif f["restore"].value is not None:
            print("Clicked on RESTORE button")
            message = "Original Model Restored."
            upload(model)

            print model["params"]["weights"]["BoostWeightScore"]

            originalfeaturesform = createFeatureForm(model)
            f = originalfeaturesform()

        elif f["download"].value is not None:
            print("Clicked on DOWNLOAD button")

            web.header("Content-Type", "json")
            web.header("Content-Disposition", "attachment; filename=newmodel.json")
            message = "Downloading Current Model..."
            newmodel = saveState(f)
            return json.dumps(newmodel,sort_keys=True, indent=4)

        return render.features(f, message)

if __name__ == "__main__":
    app = web.application(urls, globals())
    app.run()

