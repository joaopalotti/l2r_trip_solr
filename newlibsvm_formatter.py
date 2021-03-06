import json
from LTRLibrary import LTRLibrary
import misc

PAIRWISE_THRESHOLD = 1.e-1
FEATURE_DIFF_THRESHOLD = 1.e-6

class LibraryFormatter(LTRLibrary):

    def reProcessQueryDocFeatureVector(self, min_max, trainingFile):
        fout = open(trainingFile + ".tmp", "w")

        with open(trainingFile, "r") as fin:
            for f in fin:
                fields = f.strip().split(" ")
                rel = float(fields[0])
                query = int(fields[1].split(":")[1])
                fv = {}
                for i in range(2, len(fields)):
                    feat = fields[i]
                    fid, fvalue = feat.split(":")
                    min_ = min_max[self.featureIdToName[int(fid)]]["min"]
                    max_ = min_max[self.featureIdToName[int(fid)]]["max"]
                    delta = max_ - min_

                    if abs(delta) <= 0.00000001:
                        new_value = 0.0
                    else:
                        new_value = (float(fvalue) - min_) / delta
                    fv[int(fid)] = new_value

                misc.writeRankLibLine(rel, query, fv, fout)
        misc.rename(trainingFile + ".tmp", trainingFile)

    def processQueryDocFeatureVector(self,docClickInfo,trainingFile, min_max):
        with open(trainingFile,"w") as output:
            self.featureNameToId  = {}
            self.featureIdToName = {}
            self.curFeatIndex = 1
            self.curQuery = 0
            curListOfFv = []
            curQueryAndSource = ""
            for query,docId,relevance,source,featureVector in docClickInfo:
                if curQueryAndSource != query + source:
                    #Time to flush out all the pairs
                    misc.writeRankLib(curListOfFv,output,self.curQuery);
                    misc.save_mm(curListOfFv, self.featureIdToName, min_max)
                    curListOfFv = []
                    curQueryAndSource = query + source
                    self.curQuery += 1

                curListOfFv.append((relevance,self._makeFeaturesMap(featureVector)))
            misc.writeRankLib(curListOfFv,output,self.curQuery) #This catches the last list of comparisons

    def convertLibraryModelToLtrModel(self,libSvmModelLocation,outputFile,modelName,featureStoreName, useMinMax, min_max):
        content = {}

        content["class"] = "org.apache.solr.ltr.model.LinearModel"
        content["store"] = str(featureStoreName)
        content["name"] = str(modelName)
        content["features"] = []

        for featKey in self.featureNameToId.keys():
            if useMinMax:
                min_, max_ = min_max[featKey]["min"], min_max[featKey]["max"]

                if abs(max_ - min_) < 0.000000001:
                    max_ += 0.01

                norm = {"class": "org.apache.solr.ltr.norm.MinMaxNormalizer",  "params":{ "min": str(min_), "max": str(max_) } }
                content["features"].append({"name" : featKey, "norm": norm})

            else:
                content["features"].append({"name" : featKey})

        content["params"] = {"weights":{}}
        print content

        with open(libSvmModelLocation, 'r') as inFile:
            lastline = inFile.readlines()[-1]
        results = lastline.split(" ")
        results = dict( map(float, r.split(":")) for r in results[1:-1])

        #newParamVal = float(line.strip())
        for i in range(1, len(self.featureIdToName)+1):
            content["params"]["weights"][self.featureIdToName[i]] = 0.0 if i not in results else results[i]

        with open(outputFile,'w') as convertedOutFile:
            json.dump(content, convertedOutFile, sort_keys=False, indent=4)

