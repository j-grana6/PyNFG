from framework_edit2 import Flight
from GDP_edit2 import build_net
from collections import defaultdict


a = Flight(1220, 'at', 7, 0, 117)
b = Flight(1123, 'sw', 6, 15, 137)
c = Flight(422, 'sw', 13, 15, 137)
d = Flight(1454, 'sw', 15, 15, 137)
e = Flight(3750, 'sw', 21, 30, 122)
f = Flight(26, 'at', 23, 30, 117)
g = Flight(1344, 'sw', 26, 35, 137)
h = Flight(3135, 'sw', 40, 40, 137)
i = Flight(2269, 'sw', 39, 45, 137)
j = Flight(364, 'sw', 47, 50, 137)
k = Flight(779, 'sw', 50, 55, 137)
l = Flight(541, 'sw', 55, 55, 137)
m = Flight(1219, 'at', 47, 56, 117)

net = build_net([a, b, c, d, e, f, g, h, i, j, k, l, m],
                [0, 12, 24, 36, 48, 60])
# Intelligence Parameters
S = 10
M = 50


#@profile
def intel_gdp(net, S, M):
    exclude_not_strats = [nd.name for nd in net.node_dict.values()
                   if nd.player == 'nature']
    social_welfares = []
    aline_nodes = [nd for nd in net.node_dict.values()
                   if nd.player != 'nature']
    aline_names = [nd.name for nd in aline_nodes]
    # Get the airline nodes
    exclude1 = aline_names + ['Type Draw']
    # Don't sample these nodes when iterating through theta
    allocate_nodes = [nd for nd in net.node_dict.values() if
                      nd.name[-8:] == 'allocate']
    allocate_names = [nd.name for nd in allocate_nodes]
    # Don't sample these nodes, we might be able to avoid computation
    bid_nodes = [nd for nd in net.node_dict.values() if
                      nd.name[-3:] == 'bid']
    FAA_type_alls = defaultdict(set)
    #FAA_type_alls = dict(zip(range(net.node_dict['Type Draw'].CPT.shape[0]),
    #                     [set()] * net.node_dict['Type Draw'].CPT.shape[0]))
    # Remember type contingent FAA allocations of spots so that we can
    # recall old ones and avoid the binary integer programming problem
    # Keys are the type index, values are sets of allocation strings.
    # For example, a key might be 0, which corresponds to the first
    # element in the space of theta.  A value would be swatatsw, which
    # means sw gets first slow, at gets second slot...and so on.
    airline_allocations = defaultdict(set)
    ### Keys are str(type index)+str(FAA_allocation), values are dicts that
    # are the result of net.get_values.  A key might be 0swatswsw which
    # means that the theta is the first element in the space and
    # swatswsw are slot allocations.  The values are dictionaries
    # which tell how each airline allocates given a type and slots
    res_nodes = ['Airline_Delay_Costs', 'social cost']
    # Sample these nodes if allocate nodes are remembered
    # and not sampled
    intels = defaultdict(list)
    intels_second_price = defaultdict(list)
    al_strats = {nd : [] for nd in aline_names}
    al_costs = {nd[:-5] +'cost' : [] for nd in aline_names}
    al_costs_second_price  = {nd[:-5] + 'cost' : [] for nd in aline_names}
    bid_exclude = exclude1 + allocate_names + res_nodes
    for s in range(S):
        print s
        Sdict = {nd + 'cost': 0 for nd in aline_names}
        Sdict_second_price = {nd + 'cost': 0 for nd in aline_names}
        # Keep track of strategy costs
        Sdict['social_welfare'] = 0
        # Keep track of social welfare
        net.sample(exclude=allocate_names)
        # Sample the airline strategies
        sampled_strats = net.get_values(nodenames=aline_names)
        # Remember those strategies
        for theta in net.node_dict['Type Draw'].space:
            # We need to loop through types, holding the strategy
            # constant.  So we will set the value of Type_Draw
            # and then sample the net, holding the strategy constant
            # We "sample" but all of the nodes besides exclude
            # are DeterNodes
            net.set_values({'Type Draw': theta})
            # Set theta
            ptheta = net.node_dict['Type Draw'].prob()
            # Get the probability of theta
            cpt_ix = net.node_dict['Type Draw'].get_CPTindex()[0]
            # Where in the space of theta are we?
            net.sample(exclude=exclude1 + allocate_names)
            # Froma  strategy, this sample gets the type contingent bid
            # as well as the FAA allocation.
            # Now we want to see if we already sampled the type/allocation
            # pair.  If so, the airlines already know their optimal slot
            # allocation and we can just grab it from a dict
            if (''.join(net.node_dict['FAA'].value[0]) in
                    FAA_type_alls[cpt_ix]):
                net.set_values(airline_allocations[str(cpt_ix) +
                    ''.join(net.node_dict['FAA'].value[0])])
                # Sets the value of the allocate nodes
                net.sample(start=res_nodes)
                # Once the airlines allocate (solve BIP program),
                # we need to get the costs.
            else:
                # Here we need to sample the allocate nodes and the
                # rest of the net.  Then add to FAA allocation dict
                # as well as airline allocation dict.
                net.sample(start=allocate_names)
                FAA_type_alls[cpt_ix].add(
                    ''.join(net.node_dict['FAA'].value[0]))
                airline_allocations[str(cpt_ix) +
                    ''.join(net.node_dict['FAA'].value[0])] = \
                    net.get_values(allocate_names)
            Sdict['social_welfare'] += ptheta * \
                net.node_dict['social cost'].value
            # Computed the weighted social welfare
            for aline in aline_names:
                Sdict[aline+'cost'] += ptheta * \
                    net.utility(net.node_dict[aline].player)[0]
                Sdict_second_price[aline + 'cost'] += ptheta * \
                    net.utility(net.node_dict[aline].player)[1]
            # Update social welfare and costs
        social_welfares.append(Sdict['social_welfare'])
        num_better = {net.node_dict[nd].name: 0 for
            nd in aline_names}
        num_better_second_price = {net.node_dict[nd].name: 0 for
            nd in aline_names}
        # This keeps track of the number of strategies
        # that s is better than.
        for aline in aline_names:
            al_strats[aline].append(sampled_strats[aline])
            al_costs[aline[:-5] +'cost'].append(Sdict[aline+'cost'])
            al_costs_second_price[aline[:-5] + 'cost'].append(
                Sdict_second_price[aline + 'cost'])
            # Now we sample alternative strategies for each airline
            net.set_values(sampled_strats)
            # Reset net to original strategies
            for m in range(M):
                # For each alternative strategy
                ux_prime = 0
                ux_prime_second_price = 0
                # Initiate utility
                net.sample(nodenames=[aline], exclude = exclude_not_strats)
                # Sample a new strategy
                for theta in net.node_dict['Type Draw'].space:
                    cpt_ix = net.node_dict['Type Draw'].get_CPTindex()[0]
                    net.set_values({'Type Draw': theta})
                    ptheta = net.node_dict['Type Draw'].prob()
                    for nd in bid_nodes:
                        nd.draw_value()
                    net.node_dict['FAA'].draw_value()
                    # This  picks the type contingent
                    # bid and does the FAA allocation
                    if (''.join(net.node_dict['FAA'].value[0]) in
                        FAA_type_alls[cpt_ix]):
                        net.set_values(airline_allocations[str(cpt_ix) +
                            ''.join(net.node_dict['FAA'].value[0])])
                    # Sets the value of the allocate nodes
                        net.sample(start=res_nodes)
                    else:
                        # Here we need to sample the allocate nodes and the
                        # rest of the net.  Then add to FAA allocation dict
                        # as well as airline allocation dict.
                        net.sample(start=allocate_names)
                        FAA_type_alls[cpt_ix].add(
                            ''.join(net.node_dict['FAA'].value[0]))
                        airline_allocations[str(cpt_ix) +
                            ''.join(net.node_dict['FAA'].value[0])] = \
                            net.get_values(allocate_names)
                    ux_prime += ptheta * \
                        net.utility(net.node_dict[aline].player)[0]
                    ux_prime_second_price += ptheta * \
                        net.utility(net.node_dict[aline].player)[1]
                if ux_prime < Sdict[aline+'cost']:
                    num_better[aline] += 1
                if ux_prime_second_price < Sdict_second_price[aline+'cost']:
                    num_better_second_price[aline] += 1
            intels[aline].append(num_better[aline])
            intels_second_price[aline].append(num_better[aline])
        # We are going to want to return: strategies, intelligences, theta, social welfare, airline costs
    return net, intels, intels_second_price, social_welfares, \
      net.node_dict['Type Draw'].CPT, net.node_dict['Type Draw'].space, \
      al_strats, al_costs, al_costs_second_price


#res = intel_gdp(net, S, M)

#@profile
def doitall(num):
    from framework_edit2 import Flight
    from GDP_edit2 import build_net
    from collections import defaultdict
    #from gdp_intel import intel_gdp
    a = Flight(1220, 'at', 7, 0, 117)
    b = Flight(1123, 'sw', 6, 15, 137)
    c = Flight(422, 'sw', 13, 15, 137)
    d = Flight(1454, 'sw', 15, 15, 137)
    e = Flight(3750, 'sw', 21, 30, 122)
    f = Flight(26, 'at', 23, 30, 117)
    g = Flight(1344, 'sw', 26, 35, 137)
    h = Flight(3135, 'sw', 40, 40, 137)
    i = Flight(2269, 'sw', 39, 45, 137)
    j = Flight(364, 'sw', 47, 50, 137)
    k = Flight(779, 'sw', 50, 55, 137)
    l = Flight(541, 'sw', 55, 55, 137)
    m = Flight(1219, 'at', 47, 56, 117)
    net = build_net([a, b, c, d, e, f, g, h, i, j, k, l, m],
                    [0, 12, 24, 36, 48, 60])
    res = intel_gdp(net, 100, 50)
    return res

result = doitall(1)

 # The comments below are all inner monologue.  I will delete them
        #
        # At this level, compute the intelligence of each strategy profile
        # This involves dividing finding the intelligence of each airline's
        # strategy.  Then assign a (relative) probability.  We  also
        # want to keep track of airline costs.  Do we care about the distribution
        # over the slots?  What else?

        # However, I think we can permute strategies.  In other words,
        # we can compute the intelligence of any profile in which the individual
        # strategy intelligences are computed.  Then we can combine strategy profiles
        # and then compute their intelligence and then we just need to compute the new
        # social cost which we have an analytical solution for.  That way we can compute
        # j intelligences per player.  If we have n players then that is a total of n^j
        # strategy profiles.

        # No actually you can't do that.  Consider the case where one of the strategies
        # for one of the players is really bad.  Then a bad (but not as bad) strategy for
        # the other player will receive high intelligence.  We cannot mix this intelligence
        # with another because it is computed against the really bad strategy.  The only way
        # a strategy should receive high probability is if it's good and the opponent's strategy is good.  

        # Furthermore, we can do the same with type contingent profiles for a player.
        # For example, we can compute the intelligence of a type contingent strategy.
        # Then we can permute the type contingent strategies.  For example, suppose each player
        # can be 1 of k types and that we compute the intelligence of each type contingent
        # strategy m times.  But the question becomes, how do you weight the intelligences of
        # each type contingent strategy?  This I think blurs the line between the agent/player
        # representation stuff.  
