import numpy as np
from get_data import get_data

def get_posterior(res, auction='First', S=200, gamma=3):
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
    #print np.mean(sw)
    costs = []
    for _, val in res[-1].iteritems():
       costs.append(val)
    costs = np.asarray(costs)
    t_al_c = np.sum(costs, axis =0)
    #print t_al_c
    normalizing = 1. / np.cumsum(posterior)
    tc = sw - t_al_c
    running_sw = np.cumsum(np.asarray(tc) * posterior) * normalizing
    return running_sw

def get_rbs_sw(net, data, res, gdpdivide=4):
    alines = list(set(list(data.CARRIER.values)))
    gdp_len = len(sorted(list(data.arr))[::gdpdivide])
    srtd_df = data.sort('arr')
    winners = list(srtd_df.CARRIER.values[:gdp_len])
    no_bid = dict(zip(alines, [0]*len(alines)))
    net.set_values({'FAA': (np.asarray(winners), no_bid, no_bid)})
    scs = []
    net.node_dict['Type Draw'].CPT=res[3]
    alcosts = dict(zip(alines, [0]*len(alines)))
    #print alcosts
    net.sample(start = ['FAA'], exclude = ['FAA'])
    for elem in net.node_dict['Type Draw'].space:
        net.set_values({'Type Draw': elem})
        net.sample(start = ['FAA'], exclude = ['FAA'])
        scs.append(net.node_dict['social cost'].value * net.node_dict['Type Draw'].prob())
        #print net.utility('CO'),  net.utility('DL')
        for al in alines:
            
            #alcosts[al].append(net.node_dict['Type Draw'].prob() * net.utility(al)[0])
            # print al
            #alcosts[al].append((1./36) * net.utility(al)[0])
            #print net.utility('CO')[0] == net.utility('DL')[0]
            alcosts[al] += net.node_dict['Type Draw'].prob() * net.utility(al)[0]
            #alcosts[al] += 1/36. * net.utility(al)[0]
            #print net.utility(al), al
        #print alcosts['CO'][-1],  alcosts['DL'][-1]
            
    tc = np.sum(scs)
    #print np.mean(alcosts['CO'])
    #print np.mean(alcosts['DL'])
    #print np.sum(alcosts['CO'])/36.
    for al in alcosts.keys():
       tc += np.sum(alcosts[al])

    return scs, alcosts, tc
    
def compare_welfare(res, dname, gamma=12, maxtime=60, mintime=0, gdpdivide= 4, auction='First'):
    
    d = get_data(dname, maxtime=maxtime, mintime=mintime, gdpdivide=gdpdivide)
    for r in res:
        rbs = get_rbs_sw(d[0], d[1], r, gdpdivide=gdpdivide)[-1]
        pgt_auction = plot_sw_convergence(r, gamma=gamma, auction=auction)[-1]
        print rbs, pgt_auction

