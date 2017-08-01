from subprocess import call
import json
import minmax as mm
import os, sys

PAIRWISE_THRESHOLD = 1.e-1
FEATURE_DIFF_THRESHOLD = 1.e-6

class LibSvmFormatter:

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

                _writeRankLibLine(rel, query, fv, fout)
        _rename(trainingFile + ".tmp", trainingFile)

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
                    _writeRankLib(curListOfFv,output,self.curQuery);
                    _save_mm(curListOfFv, self.featureIdToName, min_max)
                    curListOfFv = []
                    curQueryAndSource = query + source
                    self.curQuery += 1

                curListOfFv.append((relevance,self._makeFeaturesMap(featureVector)))
            _writeRankLib(curListOfFv,output,self.curQuery) #This catches the last list of comparisons

    def _makeFeaturesMap(self,featureVector):
        '''expects a list of strings with "feature name":"feature value" pairs. Outputs a map of map[key] = value.
        Where key is now an integer. libSVM requires the key to be an integer but not all libraries have
        this requirement.'''
        features = {}
        for keyValuePairStr in featureVector:
            featName,featValue = keyValuePairStr.split("=");
            features[self._getFeatureId(featName)] = float(featValue);
        return features

    def _getFeatureId(self,key):
        if key not in self.featureNameToId:
                self.featureNameToId[key] = self.curFeatIndex;
                self.featureIdToName[self.curFeatIndex] = key;
                self.curFeatIndex += 1;
        return self.featureNameToId[key];

    def convertLibSvmModelToLtrModel(self,libSvmModelLocation,outputFile,modelName,featureStoreName, useMinMax, min_max):
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

def _writeRankLibLine(rel, query, fv, output):
    line = "%.1f qid:%d" % (rel, query)
    for k,v in sorted(fv.iteritems()):
        line += " %s:%s" % (k,v)
    line += "\n"
    output.write(line)

def _save_mm(listOfDocs, idtoname, min_max):
    for doc in listOfDocs:
        fv = doc[1]
        mm.save_min_max(fv, idtoname, min_max)

def _writeRankLib(listOfFeatures,output,curQuery):
    for i in range(0,len(listOfFeatures)):
        doc = listOfFeatures[i]
        rel = float(doc[0])
        fv = doc[1]
        _writeRankLibLine(rel, curQuery, fv, output)

def outputLibSvmLine(sign,fvMap,outputFile):
    outputFile.write(sign)
    for feat in fvMap.keys():
        outputFile.write(" " + str(feat) + ":" + str(fvMap[feat]));
    outputFile.write("\n")

def _rename(filein, fileout):
    try:
        cmd = " ".join(["mv", filein, fileout])
        retcode = call(cmd, shell=True)
        if retcode < 0:
            print >>sys.stderr, "Child was terminated by signal", -retcode
        else:
            print >>sys.stderr, "Child returned", retcode
    except OSError as e:
        print >>sys.stderr, "Execution failed:", e
