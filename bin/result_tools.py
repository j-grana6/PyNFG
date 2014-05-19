import numpy as np

def get_posterior(res, auction='First', S=50, gamma=6):
    """For 1 result instance"""
    als = res[0].keys()
    if auction == 'First':
        better_than = res[0]
    else:
        better_than = res[1]
    all_intels = np.asarray(better_than.values())
    all_intels = all_intels/float(S)
    posterior = np.prod(all_intels, axis=0)
    return posterior

def plot_sw_convergence(res):
    posterior = get_posterior(res)
    sw = res[2]
    normalizing = 1. / np.cumsum(posterior)
    running_sw = np.cumsum(np.asarray(sw) * posterior) * normalizing
    return running_sw
