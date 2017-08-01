import json

def setupMinMax(featuresFile, min_max):
    with open(featuresFile, "r") as f:
        feat = json.load(f)
    for f in feat:
        min_max[f["name"]] = {"min":10000000.0, "max":0.0}

def save_min_max(features, idtoname, min_max):
    print features
    for k,v in features.iteritems():
        name = idtoname[k]
        v = float(v)
        min_max[name]["max"] = max(min_max[name]["max"], v)
        min_max[name]["min"] = min(min_max[name]["min"], v)

