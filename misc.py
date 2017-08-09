import sys
import pickle
import minmax as mm
from subprocess import call

def writeRankLib(listOfFeatures,output,curQuery):
    for i in range(0,len(listOfFeatures)):
        doc = listOfFeatures[i]
        rel = float(doc[0])
        fv = doc[1]
        writeRankLibLine(rel, curQuery, fv, output)

def writeRankLibLine(rel, query, fv, output):
    line = "%.1f qid:%d" % (rel, query)
    for k,v in sorted(fv.iteritems()):
        line += " %s:%s" % (k,v)
    line += "\n"
    output.write(line)

def save_mm(listOfDocs, idtoname, min_max):
    for doc in listOfDocs:
        fv = doc[1]
        mm.save_min_max(fv, idtoname, min_max)

def outputLibSvmLine(sign,fvMap,outputFile):
    outputFile.write(sign)
    for feat in fvMap.keys():
        outputFile.write(" " + str(feat) + ":" + str(fvMap[feat]));
    outputFile.write("\n")

def rename(filein, fileout):
    try:
        cmd = " ".join(["mv", filein, fileout])
        retcode = call(cmd, shell=True)
        if retcode < 0:
            print >>sys.stderr, "Child was terminated by signal", -retcode
        else:
            print >>sys.stderr, "Child returned", retcode
    except OSError as e:
        print >>sys.stderr, "Execution failed:", e

def pickle_obj(filename, obj):
    with open(filename, "w") as f:
        pickle.dump(obj, f)

def load_pickle(filename):
    with open(filename, "r") as f:
        return pickle.load(f)

