

def doitall(NN):
    import numpy as np
    from cvxopt import matrix
    from cvxopt.glpk import ilp, options
    from collections import defaultdict
    import time
    import pynfg as pynfg
    from itertools import product

    class Flight(object):
        """
        Provides a framework for all flights

        Parameters
        ----------

        number : int
            The flight number.

        airline : str
            The airline of the flight.

        arr_time : float
            The pre-GDP arrival time of the flight.  The number is a float
            representing the number of minutes after the GDP program the flight is
            set to arrive.

        num_passengers : int
            The number of passengers on a flight
        """

        def __init__(self, number, airline, arr_time, cta, num_passengers):
            self.number = number
            self.airline = airline
            self.arr_time = arr_time
            self.num_passengers = num_passengers
            self.cta= cta

            #    def __repr__(self):
            #        return self. airline + ' Flight ' + str(self.number)


    class Airline(object):
        """
        Provides a framework to analyze airlines

        Parameters
        ----------

        name : str
            The name of the airline

        flights : list
            A list of Flight instances

        GDP_Slots : list
            All GDP slots the airline can bid on

        theta : tuple
            First element is cancellation cost (either 60 or 120), second element
            is delay cost parameters (either 'low', 'base' or 'high')
    
        """

        def __init__(self, name, flights, GDP_slots, theta_space):
            self.name = name
            self.flights = flights
            self.GDP_slots = GDP_slots
            self.theta_space = theta_space
            self.flight_arrival_times = [fl.arr_time for fl in self.flights] # These are ERTA
            self.ctas = [fl.cta for fl in self.flights] #cta
            self.budget = self._get_budget()


        def allocate_slots(self, slots_awarded, theta, d_multiplier = 1, delta=.24):
            """
            Solves the binary integer programming problem to best allocate
            GFP slots. It returns the total cost of the optimal allocation.

            Parameters
            ----------

            allslots_awarded : list
                The time slots available to the airline.  Times are given
                in minutes after the start of the GDP program.


            Returns
            -------

            al_cost : float
                The total delay cost for the airline (excluding bid cost)

            social_cost : float
                The social cost as a result of the airlines allocation

            Notes
            -----

            This function is an *effin beast*.  I already tested it but a formal test script
            would be a meaningful addition.
            """
            flight_arrival_times = self.flight_arrival_times
            delay_times = self.ctas
            num_passengers = np.asarray([fl.num_passengers for fl in self.flights]) * .869
            # From pg 27.  WE only need to enter capacity, not num passangers
            # How many slots are in the GDP
            num_slots = len(slots_awarded)
            # How many flights does the airline need to schedule
            num_flights = len(flight_arrival_times)

            # All possible allocations for a flight.  A flight can either have a
            #slot or be canceled.

            flight_slots = num_slots + num_flights
            c = []
            for elem in delay_times:
                c.append(np.concatenate(((np.asarray(slots_awarded) - elem),
                                         np.ones(len(flight_arrival_times)) *
                                         theta[0])))
            cprime = []
            for elem in flight_arrival_times:
                cprime.append(np.concatenate(((np.asarray(slots_awarded) - elem),
                                         np.ones(len(flight_arrival_times)) *
                                         theta[0])))

                # c is the minutes late for all flights for each slot.  For example, if an
                # airline has 3 GDP slots and 5 flights, the first 8 elements
                # of c correspond to the minute delay of allocating the first
                # flight to that slot.  Each flight has its own
                # 'cancellation'  slot.  Therefore, the size of c is
                # (num_slots + num_flights)*num_flights.

            c = np.squeeze(c).flatten()
            cprime = np.squeeze(cprime).flatten()
            # 2/22/14 Because ERTA might be different than CTA, we need to account for flights
            # that actually arrive early and set them to have 0 delay minutes.
            # Note that some elements where c is 0 means an allocation is impossible,
            # but some are possible.  Therefore, we need a c for delay costs and we need
            # a cprime for earliest arrival times. We get "possible" allocations with cprime
            # but compute costs with c.
            early = c <= 0
            c[early] = 0
            ones_vec = np.ones(flight_slots)

            ##  G1 - Only assigns flights to slots that are after scheduled time:
            # Note that this uses c, which are times, not C which are costs.
            G1 = np.zeros((len(flight_arrival_times), len(cprime)))
            for fl in range(len(flight_arrival_times)):
                G1[fl, fl*len(ones_vec): (fl+1)*len(ones_vec)] = \
                    cprime[fl*(flight_slots): (fl+1)*(flight_slots)]
            # Here we need to use cprime because the constraint is the flights cannot
            # arrive before their ERTA, but delay is computed from CTA.  ERTA might be
            # before CTA, kinda like in Die Hard 2 when the planes are jusr circling
            # overhead.  


            # Multiply by -1 since inequality is a less than and costs are
            # reported as positive numbers.
            G1 = -1 * G1
            h1 = np.zeros(num_flights)

            # Each flight must be scheduled to one and only one slot
            A1 = np.zeros((len(flight_arrival_times), len(c)))
            for fl in range(len(flight_arrival_times)):
                A1[fl, fl*len(ones_vec): (fl+1)*len(ones_vec)] = ones_vec
            b1 = np.ones(num_flights)

            # At most one flight per slot
            G2 = np.zeros((num_slots + num_flights, len(c)))
            for slot in range(flight_slots):
                G2[slot, np.arange(slot, len(c), flight_slots)] = 1

            h2 = np.ones(num_flights + num_slots)

            G = matrix(np.vstack((G1, G2)))
            h = matrix(np.hstack((h1, h2)))
            A = matrix(A1)
            B = matrix(b1)
            C = matrix(delay_cost(np.asarray(c), theta[1]) * c ) #cost/min * mins
            Binary = set(range(len(c)))

            options['LPX_K_MSGLEV'] = 1  # TODO: Change to errors only
            mod = ilp(C, G, h, A, B, B=Binary)

            res = np.asarray(mod[1])
            al_cost = np.mat(C).T * np.asarray(res)
            num_passengers = np.tile(num_passengers, (flight_slots,1)).T.flatten()
            #  ^ Matches shape of cost vector
            #social_cost = delta * np.dot(res.flatten()*((.9986 + .0132*c.T)*c.T), num_passengers)
            social_cost =  delta * np.dot(res.flatten()*c.T, num_passengers)

            return np.float_(al_cost), np.float_(social_cost)

        def _get_budget(self):
            """ Computes the budget for airline bids

            Parameters
            ----------

            slot_times_remaning : list
                A list where each element is the post GDP slots that the airline
                can bid for.  Times are expressed as minutes after the GDP program


            """

            budget = {}
            for theta in self.theta_space:
                max_cost_per_min = delay_cost(np.asarray([theta[0]]), theta[1])
                # highest cost per minute is if all flights canceled
                budget_max = max_cost_per_min * theta[0]*len(self.flights)
                budget_min = self.allocate_slots(self.GDP_slots, theta)[0]
                ### To get budget min, do a linear programming problem.
                ### assume that an airline wins all slots then minimizes the cost.
                budget[theta] = np.float(budget_max-budget_min)
            self.budget = budget
            return budget

        def draw_strat(self):
            simplex_draw = np.random.dirichlet(np.ones(len(self.GDP_slots)),
                                               (len(self.theta_space)))
            r = np.random.random(len(self.theta_space)).reshape(-1,1)
            bid = (r **(1/float(len(self.GDP_slots)))*simplex_draw)
            strat = np.asarray(self.budget.values()).reshape(-1,1)*bid
            tc_strat = dict(zip(self.budget.keys(), list(strat)))
            return tc_strat, 1





    def delay_cost(time_delayed, airline_type):
        """

        The three polynomials from the 2004 Westminster paper are:


        Low = -.10005128x +.01022564x^2
        Base = -.2325641x + .02128205x^2
        High =  .82851282x +.01854359x^2
        """
        above_max = time_delayed > 65
        time_delayed[above_max] = 65
        euro_to_dollar = .9916
        inflation = 1.22

        if airline_type == 'low':
            cost =   -.10005128 * time_delayed + .01022564*time_delayed**2
        elif airline_type == 'base':
            cost =  -.2325641*time_delayed + .02128205*time_delayed**2
        elif airline_type == 'high':
            cost =  .82851282*time_delayed + .01854359*time_delayed**2

        cost[cost<0] = 0
        return cost * inflation * euro_to_dollar

    def faa_slot_selection(al_instances, bid_nodes, times):
        """ Allocates slots based on bids

        Parameters
        ----------

        al_nodes : dict
            Keys are airline names, values are Airline instance DeterNode

        bid_nodes : dict
            Keys are airline names, values are Airline instance DecisionNode

        times : list
            THe list of GDP times available

        """

        bnodes = bid_nodes.values()
        airlines = bid_nodes.keys()  # Maintaining Order
        slot_counts = dict.fromkeys(airlines, 0)
        bids = np.asarray([b.value for b in bnodes])
        winners = []
        bid_costs = dict.fromkeys(airlines, 0)
        for slot in range(len(times)):
            slot_bids = bids[:, slot]
            ix = np.argsort(slot_bids)
            sorted_airlines = np.asarray(airlines)[ix][::-1]
            sorted_bids = slot_bids[ix][::-1]
            ctr=0
            for al in sorted_airlines:
                if slot_counts[al] < sum(np.asarray(al_instances[al].flight_arrival_times)
                                         <= times[slot]):
                    bid_costs[al] += sorted_bids[ctr] # To make second price, change to ctr + 1
                    winners.append(al)
                    slot_counts[al] +=1
                    ctr +=1
                    break
                else:
                    ctr+=1
        winners  = np.asarray(winners)
        return winners, bid_costs

    def build_net(flights, gdp_times,
                  theta_space=list(product([60, 120], ['low', 'base', 'high']))):
        """
        Generates the net.

        Note that the 'modified' net is needed.



        Parameters
        ----------

        gdp_times : list
            List of GDP times in minutes after GDP announcement.  Order is
            earliest to latest.

        flights : list
            A list of flight instances scheduled during the GDP program

        theta_space : list
            The possible types of an airline

        """
        ###################### Initialize Some Parameters###########################

        num_airlines = len(set([fl.airline for fl in flights]))



        ##################################Create airline instances####################
        # This allows us to easily manage multiple airlines

        # This loop groups the flights by airline in a dict
        airlines = {}
        for fl in flights:
            try :
                airlines[fl.airline].append(fl)
            except KeyError:
                airlines[fl.airline] = [fl]

        type_dist = {}
        for al in airlines:
            ## For eacha airline, *independently* draw type distribution.
            ## Note we cannot just draw from the simplex over all possible type
            ## profiles.  This is because the Dirichlet Distribution can generate
            ## impossible type profiles.  For example, if both players have 2 types,
            ## A and B, the Dirichlet distribution can generate P(AA)=.5, P(BB) = .5
            ## However, it is impossible to generate this from independent .  
            prob_60 = np.random.random()
            prob_120 = 1-prob_60
            prob_l_b_h = np.random.dirichlet(np.ones(3), 1).flatten()
            type_dist[al] = {'low': prob_l_b_h[0], 'base': prob_l_b_h[1],
                             'high' : prob_l_b_h[2], 60: prob_60, 120: prob_120}
        chance_space = list(product(theta_space, repeat = num_airlines))
        chance_dicts = []
        for game in chance_space:
            chance_dicts.append(dict(zip(airlines.keys(), game)))

        alpha = []
        for game in chance_dicts:
            al_probs = []
            for al in game:
                al_probs.append(type_dist[al][game[al][0]]*type_dist[al][game[al][1]])
            alpha.append(np.prod(al_probs))
        alpha = np.asarray(alpha)


            # This function randomly draws a common prior

        ############################################################################


        ##################### Chance node that picks player types ##################
        cn1 = pynfg.ChanceNode('Type Draw', CPTip = (alpha, [], chance_dicts))
        # This creates the chance node
        cn1.draw_value()

        ############################################################################





        def create_airline_inst(name, flights):
            """ Returns an airline instance

            Parameters
            ----------

            name : str
                The airline name

            cn1 : Chance_Node
                The values of the node are types

            flights : Flights
                The flights belonging to the airline

            al_num : int
                A unique integer that identifies each airline.  Must be in [0, num_airlines-1]
            """
            return Airline(name, flights, gdp_times, theta_space)


        # Here we create all of the instances

        al_instances = {}



        for al in airlines:
            al_ins = create_airline_inst(al, airlines[al])
            al_instances[al] = al_ins



        #############################Create Decision Nodes#############################

        #### For each airline, we now create a Decision Node.  The Decision is a type
        #### contingent strategy.  That is, a num_slots*num_types matrix.

        strat_nodes = {}
        def strat_func(al_class):
            return al_class.draw_strat()

        ##### Note how using an airline class makes this much easier.  For each decision
        ##### node, the parent is the Airline class.  Now to draw a bid, we only need to
        ##### call Airline.draw_strat()


        for inst in airlines:
            tc_strat = pynfg.DecisionNode(inst + 'strat', inst, strat_func,
                                     params ={'al_class': al_instances[inst]})
            tc_strat.draw_value()
            strat_nodes[inst] = tc_strat

        bid_nodes = {}

        def bid_func(al_strat, airline, cn1):
            """
            From a type contingent strategy profile, this function used
            in the bid nodes chooses the strategy that corresponds to
            the value of the chance node.
            """
            return al_strat[cn1[airline]]



        for inst in airlines:
            bid  = pynfg.DeterNode(inst + 'bid',  bid_func,
                                     params ={'al_strat': strat_nodes[inst], 'cn1': cn1,
                                              'airline': inst }, continuous=True)
            bid.draw_value()
            bid_nodes[inst] = bid





        ###############################Creating the FAA node#############################
        #### Given the bids, the FAA needs to allocate slots.  That is what the         #
        #### faa_allocate_slots function does.  It returns a list L with len(gdp_times) #
        #### such that L[i] is the airline that won slot i of GDP times.  It also       #
        #### returns a dict of bid costs where keys are airline names and values are    #
        #### costs.  Right now it is set up for first price auction but can be easily   #
        #### modified (see inline comment) to be second price auction.                  #


        FAA_params = {'al_instances': al_instances, 'bid_nodes': bid_nodes, 'times': gdp_times}
        FAA_parents = bid_nodes.values()
        FAA = pynfg.DeterNode('FAA', faa_slot_selection, FAA_params,continuous=True,
                              parents = FAA_parents)
        FAA.draw_value()
        ## Note I added parents to the DeterNode.  See the notebook for why.


        ############################## Airlines allocate slots ##########################
        # Airlines now need to solve the binary integer programming problem.  That is   #
        # what the following code generates. For each airline, there is a deterministic #
        # node with function allocate_slots.  The function takes as an input the FAA    #
        # allocations AND the Airline class instance.  Since each airline has a method  #
        # allocate slots, that takes as an input the slots awarded to it (Remember      #
        # flight information is stored in each airline upon instantiation) and solves   #
        # the binary integer programming problem.  The output is not necessarily the    #
        # strategy (although this wouldn't be hard to add).  Instead, it is the delay   #
        # cost and the airline's contribution to social cost.                           #



        al_allocate_nodes = {}

        def pick_slots(faa, airline, cn1):
            slots = np.asarray(gdp_times)[faa[0]==airline.name]
            return airline.allocate_slots(slots, cn1[airline.name])

        ## Again, notice the benefit of using an Airline class.  To solve the binary
        ## integer programming problem, all we have to do is call a class method
        ## for each airline.


        for al in airlines:
            allocate_params = {'faa': FAA, 'airline': al_instances[al],
                               'cn1': cn1}
            assign_flights = pynfg.DeterNode(al + ' allocate', pick_slots,
                                             params=allocate_params, continuous=True)
            assign_flights.draw_value()
            al_allocate_nodes[al] = assign_flights


        #### This is considered a helper node.  It stores all Airline delay costs.    #
        #### Creating such a node allows us to create utility functions by iterating  #
        #### through players.

        def all_costs():
            cst_keys = al_allocate_nodes.keys()
            cst_values = al_allocate_nodes.values()
            csts = map(lambda x: x.value[0], cst_values)
            return dict(zip(cst_keys, csts))
        cost_nodes = pynfg.DeterNode('Airline_Delay_Costs', all_costs, params = {},
                                     parents = al_allocate_nodes.values(), continuous =True)
        cost_nodes.draw_value()
        ###################################Social cost#################################
        # The social cost is just the sum of the social costs contributed by each     #
        # airline.                                                                    #


        def calc_social_c(indiv_sc):
            """ Sums social costs

            Parameters
            ----------

            indiv_sc : Dict
                Dictionary of all Decision nodes whose output are airline and social
                costs
            """
            sc = [np.float_(al_allocate_nodes[al].value[1]) for al in al_allocate_nodes]
            return - sum(sc)

        social_cost = pynfg.DeterNode('social cost', calc_social_c,
                                      params = {'indiv_sc': al_allocate_nodes},
                                      parents = al_allocate_nodes.values(), continuous=True)
        social_cost.draw_value()
        social_cost.get_value()


        ####### Utility functions (still a pain in the ass to define through looping#####
        # The function takes as an input the FAA node as well as the Costs node. The    #
        # function then gets the value for the appropriate airline.                     #

        ufuncs = {}
        def util_wrap(airline):

            def f(FAA, Airline_Delay_Costs):
                """
                This function takes advantage of the fact that global variables
                inside of a python function are evaluated xwhen the function
                is called, not when the function is written.  Therefore, every time
                f is called _al_allocate_nodes will be the current value of
                the nodes
                """
                return -(Airline_Delay_Costs[airline] + FAA[1][airline])

            return f

        for al in airlines:
            util = util_wrap(al)

            ufuncs[al] = util


        node_list = [cn1, FAA, cost_nodes]
        node_list.extend(bid_nodes.values())
        node_list.extend(al_allocate_nodes.values())
        node_list.extend([social_cost])
        node_list.extend(strat_nodes.values())
        G = pynfg.SemiNFG(node_list, ufuncs)





        return G

    #@profile
    def intel_gdp(net, S, M, **kwargs):
        social_welfares = []
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
        for s in range(S):
            print s
            Sdict = {nd + 'cost' : 0 for nd in aline_names}
            # Keep track of strategy costs
            Sdict['social_welfare'] = 0
            # Keep track of social welfare
            net.sample(exclude = allocate_names)
            # Sample the airline strategies
            sampled_strats = net.get_values(nodenames = aline_names)
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
                net.sample(exclude = exclude1 + allocate_names)
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
                    net.sample(start = res_nodes)
                    # Once the airlines allocate (solve BIP program),
                    # we need to get the costs.  
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
                Sdict['social_welfare'] += ptheta * \
                  net.node_dict['social cost'].value
                # Computed the weighted social welfare
                for aline in aline_names:
                    Sdict[aline+'cost'] += ptheta * \
                      net.utility(net.node_dict[aline].player)
                # Update social welfare and costs
            social_welfares.append(Sdict['social_welfare'])
            num_better = {net.node_dict[nd].name: 0 for
                nd in aline_names}
            # This keeps track of the number of strategies
            # that s is better than.
            for aline in aline_names:
                # Now we sample alternative strategies for each airline
                net.set_values(sampled_strats)
                # Reset net to original strategies
                for m in range(M):
                    # For each alternative strategy
                    ux_prime = 0
                    # Initiate utility
                    net.sample(nodenames=[aline])
                    # Sample a new strategy
                    for theta in net.node_dict['Type Draw'].space:
                        cpt_ix = net.node_dict['Type Draw'].get_CPTindex()[0]
                        net.set_values({'Type Draw' : theta})
                        ptheta = net.node_dict['Type Draw'].prob()
                        net.sample(exclude = exclude1 + allocate_names + res_nodes)
                        # This  picks the type contingent
                        # bid and does the FAA allocation
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
                intels[aline].append(num_better[aline])



            # We are going to want to return: strategies, intelligences, theta, social welfare, airline costs
        return intels, social_welfares


    # Intelligence Parameters
    S = 5
    M = 5

    #res =intel_gdp(net, S, M)


    a = Flight(1220, 'at', 7, 0, 117)
    b = Flight( 1123, 'sw', 6, 15, 137)
    c = Flight(422, 'sw', 13, 15, 137)
    d = Flight(1454, 'sw', 15, 15, 137)
    e = Flight(3750, 'sw', 21, 30, 122)
    f = Flight(26, 'at', 23, 30, 117)
    g = Flight(1344, 'sw', 26, 35, 137)
    h = Flight(3135, 'sw', 40, 40, 137)
    i = Flight(2269, 'sw', 39, 45, 137)
    j = Flight( 364, 'sw', 47, 50, 137)
    k = Flight( 779, 'sw' , 50, 55, 137)
    l = Flight( 541, 'sw', 55, 55, 137)
    m = Flight(1219, 'at', 47, 56, 117)

    net = build_net([a,b,c,d,e,f,g,h,i,j,k,l,m], [0, 12, 24, 36, 48, 60])
    return intel_gdp(net, S, M)




from multiprocessing import Pool
p=Pool()
res=p.map(doitall, range(4))