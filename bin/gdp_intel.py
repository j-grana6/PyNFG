from framework_edit2 import Flight, Airline
from GDP_edit2 import build_net
from collections import defaultdict
a = Flight(10, 'sw', 25, 100)
b = Flight( 11, 'sw', 12, 120)
c = Flight(12, 'at', 9, 90)
d = Flight(13, 'at', 19, 66)

net = build_net([a,b,c,d], [31, 28])
# Intelligence Parameters
S = 100
M = 50


@profile
def intel_gdp(net, S, M):
    aline_nodes = [nd for nd in net.node_dict.values() 
                   if nd.player != 'nature']
    aline_names = [nd.name for nd in aline_nodes]
    # Get the airline nodes
    exclude1 = aline_names + ['Type Draw']
    # Don't sample these nodes when iterating through theta
   
    allocate_nodes = [nd for nd in net.node_dict.values() if
                      nd.name[-8:] =='allocate']
    allocate_names = [nd.name for nd in allocate_nodes]
    # Don't sample these nodes, we might be able to avoid computation
    FAA_type_alls = defaultdict(set)
    #FAA_type_alls = dict(zip(range(net.node_dict['Type Draw'].CPT.shape[0]),
    #                     [set()] * net.node_dict['Type Draw'].CPT.shape[0]))
    # Remember type contingent FAA allocations of spots so that we can 
    # recall old ones and avoid the binary integer programming problem
    # Keys are the type index, values are sets of allocation strings.
    airline_allocations = defaultdict(set)
    ### Keys are str(type index)+str(FAA_allocation), values are dicts that
    # are the result of net.get_values
    res_nodes = ['Airline_Delay_Costs', 'social cost']
    # Sample these nodes if allocate nodes are remembered
    # and not sampled
    for s in range(S):
        Sdict = {nd + 'cost' : 0 for nd in aline_names}
        # Keep track of strategy costs
        Sdict['social_welfare'] = 0
        # Keep track of social welfare
        net.sample(exclude = allocate_names)
        # Sample a strategy (type contingent bids)
        # In fact, we can exclude all nodes
        sampled_strats = net.get_values(nodenames = aline_names)
        # Remember those strategies
        for theta in net.node_dict['Type Draw'].space:
            # We need to loop through types, holding the strategy
            # constant.  So we will set the value of Type_Draw
            # and then sample the net, holding the strategy constant
            # We "sample" but all of the nodes besides exclude
            # are DeterNodes
            net.set_values({'Type Draw': theta})
            ptheta = net.node_dict['Type Draw'].prob()
            cpt_ix = net.node_dict['Type Draw'].get_CPTindex()[0]
            net.sample(exclude = exclude1 + allocate_names)
            # Now we want to see if we already sampled the type/allocation
            # pair.  If so, the airlines already know their optimal slot
            # allocation and we can just grab it from a dict
            if (''.join(net.node_dict['FAA'].value[0]) in
                FAA_type_alls[cpt_ix]):
                net.set_values(airline_allocations[str(cpt_ix) +
                                ''.join(net.node_dict['FAA'].value[0])])
                # Sets the value of the allocate nodes
                net.sample(start = res_nodes)
            else:
                # Here we need to sample the allocate nodes and the
                # rest of the net.  Then add to FAA allocation dict
                # as well as airline allocation dict.
                net.sample(start = allocate_names)
                FAA_type_alls[cpt_ix].add(
                    ''.join(net.node_dict['FAA'].value[0]))
                airline_allocations[str(cpt_ix) +
                    ''.join(net.node_dict['FAA'].value[0])] = \
                        net.get_values(allocate_names)
            # VVVVVVVVVVV
            #start_Theta = net.node_dict['Type Draw'].value
            #start_strat1 = net.node_dict['atstrat'].value
            # ^^^^^^^^^^^
            # VVVVVVVV
            #assert start_Theta == net.node_dict['Type Draw'].value
            #assert start_strat1 == net.node_dict['atstrat'].value
            # ^^^^^^^^
            Sdict['social_welfare'] += ptheta * \
              net.node_dict['social cost'].value
            for aline in aline_names:
                Sdict[aline+'cost'] += ptheta * \
                  net.utility(net.node_dict[aline].player)
            # Update social welfare and costs
        num_better = {net.node_dict[nd].name: 0 for
            nd in aline_names}
        # This keeps track of the number of strategies
        # that s is better than.
        for aline in aline_names:
            net.set_values(sampled_strats)
            for m in range(M):
                ux_prime = 0
                net.sample()
                for theta in net.node_dict['Type Draw'].space:
                    cpt_ix = net.node_dict['Type Draw'].get_CPTindex()[0]
                    net.set_values({'Type Draw': theta})
                    ptheta = net.node_dict['Type Draw'].prob()
                    net.sample(exclude = exclude1 + allocate_names + res_nodes)
                    # This just does the FAA allocation... i.e. picks the type contingent
                    # bid and does the FAA allocation
                    # Put modified sample here
                    if (''.join(net.node_dict['FAA'].value[0]) in
                        FAA_type_alls[cpt_ix]):
                        net.set_values(airline_allocations[str(cpt_ix) +
                            ''.join(net.node_dict['FAA'].value[0])])
                    # Sets the value of the allocate nodes
                        net.sample(start = res_nodes)
                    else:
                        # Here we need to sample the allocate nodes and the
                        # rest of the net.  Then add to FAA allocation dict
                        # as well as airline allocation dict.
                        net.sample(start = allocate_names)
                        FAA_type_alls[cpt_ix].add(
                            ''.join(net.node_dict['FAA'].value[0]))
                        airline_allocations[str(cpt_ix) +
                            ''.join(net.node_dict['FAA'].value[0])] = \
                            net.get_values(allocate_names)
                    ux_prime += ptheta * \
                        net.utility(net.node_dict[aline].player)
                if ux_prime < Sdict[aline+'cost']:
                    num_better[aline]+=1
        
intel_gdp(net, S, M)
