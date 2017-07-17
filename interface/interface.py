import web
import json
import httplib
import urllib
from web import form

render = web.template.render('templates/')

urls = (
    '/', 'index'
)

def connectQuery(searchText, host="solr65.tripdatabase.com", port="80", collection="trip", requestHandler="query",
            solrFeatureStoreName="TripFeatures", efiParams="efi.user_query=$USERQUERY efi.user_query_comma=$QUERYCOMMA",
            rerank=None, ltr_model="tripModel"):

    conn = httplib.HTTPConnection(host, port)
    headers = {"Connection":" keep-alive"}
    solrQueryUrl = "/".join([ "", "solr", collection, requestHandler ])
    solrQueryUrl += ("?fl=" + ",".join([ "Id", "score", "Title", "TitleAndBody", "Url", "SortDate", "[features store="+solrFeatureStoreName+" "+efiParams+"]" ]))
    solrQueryUrl += " ".join(["&q=",searchText])
    userQuery = urllib.quote_plus(searchText.strip().replace("'","\\'").replace("/","\\\\/"))
    userQueryComma = urllib.quote_plus(searchText.strip().replace("'","\\'").replace("/","\\\\/").replace(" ",","))

    if rerank is not None:
        #rq={!ltr%20model=exampleModel%20efi.user_query=lung%20cancer%20efi.user_query_comma=lung,cancer}
        solrQueryUrl += " ".join(["&rq=","{!ltr model= ", ltr_model])
        if rerank > 0:
            solrQueryUrl += "".join([" ","reRankDocs=", str(rerank)])
        solrQueryUrl += " ".join(["", efiParams, "}"])

    solrQuery = solrQueryUrl.replace(" ","+")
    solrQuery = solrQuery.replace('$USERQUERY', urllib.quote("\\'" + userQuery + "\\'"))
    solrQuery = solrQuery.replace('$QUERYCOMMA', userQueryComma)

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

class Doc:
    def __init__(self, id, title, url, titleAndBody, date=""):
        self.id = id
        self.title = title
        self.url = url
        self.date = date
        self.titleAndBody = titleAndBody

def transformObject(docs):
    return [ Doc(d['Id'],d['Title'],d['Url'],d['TitleAndBody'],d['SortDate']) for d in docs ]

myform = form.Form(
    form.Textbox("Query", form.notnull, id="query"),
    form.Dropdown("N", args=['All','3','5','10','20','50','100','500','1000','10000'], value='5', id="N", description="Number of documents to rerank:")
)

class index:
    def GET(self):
        f = myform()
        return render.index(f)

    def POST(self):
        f = myform()
        if not f.validates():
            return render.index(f)

        searchText = f['Query'].value
        n = 0 if f["N"].value == "All" else int(f["N"].value)
        print "Running query with: ", searchText, "reranking ",n
        docs = transformObject(connectQuery(searchText))
        docs_reranked = transformObject(connectQuery(searchText, rerank=n))

        return render.index(f, docs, docs_reranked)

if __name__ == "__main__":
    app = web.application(urls, globals())
    app.run()

