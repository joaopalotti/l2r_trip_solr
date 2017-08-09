import pickle

class LTRLibrary:

    def __init__(self):
        self.featureNameToId = {}
        self.featureIdToName = {}
        self.curFeatIndex = 0

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

    def save_pickle(self, filename):
        with open(filename, "w") as f:
            pickle.dump( (self.featureNameToId, self.featureIdToName, self.curFeatIndex), f)

    def load_pickle(self, filename):
        with open(filename, "r") as f:
            self.featureNameToId, self.featureIdToName, self.curFeatIndex = pickle.load(f)


