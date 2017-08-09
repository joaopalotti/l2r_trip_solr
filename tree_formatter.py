import json
import xml.etree.ElementTree as ET
from LTRLibrary import LTRLibrary
import misc

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

    def convertLibraryModelToLtrModel(self, libraryModelLocation, outputFile, modelName, featureStoreName, useMinMax, min_max):
        content = {}

        content["class"] = "org.apache.solr.ltr.model.MultipleAdditiveTreesModel"
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

        with open(libraryModelLocation, 'r') as inFile:
            model = inFile.readlines()

        i = 0
        while model[i].startswith("##"):
            i += 1

        model = model[i+1:]
        model = [l.strip() for l in model]
        root = ET.fromstring(' '.join(model))

        forest = []
        for child in root:
            tree = {}
            tree["weight"] = child.attrib["weight"]
            first_split = child.find("split")

            tree_dict = self.get_tree(first_split)
            tree["root"] = tree_dict

            forest.append(tree)

        content["params"] = {"trees": forest}

        with open(outputFile,'w') as convertedOutFile:
            json.dump(content, convertedOutFile, sort_keys=False, indent=4)

    def get_tree(self, tree):

        tree_dict = {}

        if tree.find("output") is not None:
            tree_dict["value"] = tree.find("output").text.strip()
            return tree_dict

        tree_dict["feature"] = self.featureIdToName[ int(tree.find("feature").text) ]
        tree_dict["threshold"] = tree.find("threshold").text.strip()

        left_tree, right_tree = None, None
        for s in tree.findall("split"):
            if s.attrib["pos"] == "left":
                left_tree = s
            if s.attrib["pos"] == "right":
                right_tree = s

        if left_tree is not None:
            left = self.get_tree(left_tree)
            tree_dict["left"] = left

        if right_tree is not None:
            right = self.get_tree(right_tree)
            tree_dict["right"] = right

        return tree_dict


