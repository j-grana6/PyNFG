import numpy as np
import pandas as pd
from framework_edit2 import *
from GDP_edit2 import *
import os


dpath = '/home/justin/Documents/papers/gdp/datasets/'
print dpath

fpath = ''.join([dpath, 'PHL20140330.xlsx'])
def get_net_params(datapath):
    data = pd.read_excel(datapath, 'final')
    data = data[data.passengers >30]
    rel_cts = data.CARRIER.value_counts()/ sum(data.CARRIER.value_counts())
    als = rel_cts[rel_cts > .1].index
    data = data[data.CARRIER.isin(als)]
    data = data[data.arr <= 180]
    data.arr = data.arr + np.random.random(len(data.arr))*.0001
    print len(data)
    num_flights = len(data.CARRIER)
    gdp_times = sorted(list(data.arr))[::2]
    print gdp_times
    flights = []
    ctr = 1
    # Used as artifact from flight instance
    for _, f in data.iterrows():
        flights.append(Flight(ctr, f.CARRIER, f.arr, f.arr, f.passengers))
        ctr +=1
    net = build_net(flights, gdp_times)
    return net

tres = get_net_params(fpath)
# i=0
# for f in os.listdir(dpath):
#     i +=1
#     #print dpath
#     fpath = ''.join([dpath, f])
#     #print fpath
#     data = pd.read_excel(fpath, 'final')
#     data= data[data.passengers>50]
#     rel_cts = data.CARRIER.value_counts()/ sum(data.CARRIER.value_counts())
#     als = rel_cts[rel_cts > .2].index
#     data = data[data.CARRIER.isin(als)]
#     print data.CARRIER.value_counts()
#     print f
from gdp_intel import intel_gdp
# import pickle
# def one_f(seed):
#     np.random.seed(seed)
#     return intel_gdp(tres, 1000, 50)

# from multiprocessing import Pool
# p = Pool()
tcase = intel_gdp(tres, 5, 50)
#pickle.dump(tcase, open('phl.p', 'wb'))
