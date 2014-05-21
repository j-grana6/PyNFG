import numpy as np

def get_posterior(res, auction='First', S=50, gamma=3):
    """For 1 result instance"""
    als = res[0].keys()
    if auction == 'First':
        better_than = res[0]
    else:
        better_than = res[1]
    all_intels = np.asarray(better_than.values())
    all_intels = (all_intels/float(S))**gamma
    posterior = np.prod(all_intels, axis=0)
    posterior = posterior / np.sum(posterior)
    return posterior

def plot_sw_convergence(res, gamma=6, auction='First'):
    posterior = get_posterior(res, gamma=gamma, auction = auction)
    sw = res[2]
    normalizing = 1. / np.cumsum(posterior)
    running_sw = np.cumsum(np.asarray(sw) * posterior) * normalizing
    return running_sw

def get_rbs_sw(net, data, res):
    alines = list(set(list(data.CARRIER.values)))
    gdp_len = len(sorted(list(data.arr))[::4])
    srtd_df = data.sort('arr')
    winners = list(srtd_df.CARRIER.values[:gdp_len])
    no_bid = dict(zip(alines, [0]*len(alines)))
    net.set_values({'FAA': (np.asarray(winners), no_bid, no_bid)})
    scs = []
    net.node_dict['Type Draw'].CPT=res[3]
    alcosts = dict(zip(alines, [[]]*len(alines)))
    net.sample(start = ['FAA'], exclude = ['FAA'])
    for elem in net.node_dict['Type Draw'].space:
        net.set_values({'Type Draw': elem})
        net.sample(start = ['FAA'], exclude = ['FAA'])
        scs.append(net.node_dict['social cost'].value * net.node_dict['Type Draw'].prob())
        for al in alines:
            alcosts[al].append(net.utility(al))
    return scs, alcosts
    
    
