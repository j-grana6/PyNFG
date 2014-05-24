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
maxtime = float(sys.argv[3])
print pdump
def get_net_params(datapath, maxtime=maxtime):
    #np.random.seed(6)
    data = pd.read_excel(datapath, 'final')
    data = data[data.passengers >30]
    rel_cts = data.CARRIER.value_counts()/ sum(data.CARRIER.value_counts())
    als = rel_cts[rel_cts > .1].index
    print rel_cts
    data = data[data.CARRIER.isin(als)]
    data = data[data.arr>=maxtime-60]
    data = data[data.arr <maxtime]
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



def get_results(seed):
    np.random.seed(seed)
    bothres = get_net_params(fpath)
    tres = bothres[0]
    return intel_gdp(tres, 800, 50)


from gdp_intel import intel_gdp
import pickle
from multiprocessing import Pool
p=Pool()


tcase = p.map(get_results, np.arange(112,119,1))

pickle.dump(tcase, open(pdump, 'wb'))
#bothres[1].to_csv(pdump +'.csv')
