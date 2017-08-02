import pandas as pd
from glob import glob

size_test = 10000

logs_datapath = "/bigdata/palotti/trip/ltr/logs/*.json"
processed_files = sorted([f.strip() for f in open("processed.txt", "r").readlines()])
processed_files_txt = open("processed.txt", "a")

df = pd.read_pickle("df.pickle")

for json_filename in sorted(glob(logs_datapath)):
    if json_filename in processed_files:
        continue
    processed_files.append(json_filename)
    processed_files_txt.write("%s\n" % (json_filename))

    with open(json_filename, "r") as f:
        content = "[" + f.read() + "]"
        dftmp = pd.read_json(content)
        df = pd.concat((df,dftmp))

df.to_pickle("df.pickle")

df.head(df.shape[0] - size_test).to_pickle("train.pickle")
df.tail(size_test).to_pickle("test.pickle")
processed_files_txt.close()


def reset_pickle(picklefilename):
    df0 = pd.read_pickle(picklefilename).head(0)
    df0.to_pickle(picklefilename)

def create_new_pickle():
    json_filename = "/bigdata/palotti/trip/ltr/logs/2017-01-01.json"
    with open(json_filename, "r") as f:
        content = "[" + f.read() + "]"
        dftmp = pd.read_json(content)
        dftmp.to_pickle("df.pickle")
    reset_pickle("df.pickle")
