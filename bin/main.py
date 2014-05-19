import numpy as np
import pandas as pd
from framework_edit2 import *
from GDP_edit2 import *
import os
import sys

#dpath = '/home/justin/Documents/papers/gdp/datasets/'
#fpath = ''.join([dpath, sys.argv[1]])
fpath = sys.argv[1]
print fpath
acode = sys.argv[2]
pdump = ''.join((acode, '.p'))
print pdump
def get_net_params(datapath):
    data = pd.read_excel(datapath, 'final')
    data = data[data.passengers >30]
    data = data[data.arr<=240]
    rel_cts = data.CARRIER.value_counts()/ sum(data.CARRIER.value_counts())
    als = rel_cts[rel_cts > .1].index
    print rel_cts
    data = data[data.CARRIER.isin(als)]
    data.arr = data.arr + np.random.random(size = len(data.arr))*.001
    print data
    num_flights = len(data.CARRIER)
    last_flight = max(data.arr)
    end_time = last_flight + 1
    gdp_times = sorted(list(data.arr))[::2]
    flights = []
    ctr = 1
    # Used as artifact from flight instance
    for _, f in data.iterrows():
        flights.append(Flight(ctr, f.CARRIER, f.arr, f.arr, f.passengers))
        ctr +=1
    net = build_net(flights, gdp_times)
    return net, data

bothres = get_net_params(fpath)
tres = bothres[0]
# for f in os.listdir(dpath):
#     i +=1
#     #print dpath
#     fpath = ''.join([dpath, f])
#     #print fpath
#     data = pd.read_excel(fpath, 'final')
#     print max(data.arr)
#     data= data[data.passengers>50]
#     rel_cts = data.CARRIER.value_counts()/ sum(data.CARRIER.value_counts())
#     als = rel_cts[rel_cts > .2].index
#     data = data[data.CARRIER.isin(als)]
    
#     print f


from gdp_intel import intel_gdp
import pickle
tcase = intel_gdp(tres, 10,50)
pickle.dump(tcase, open(pdump, 'wb'))