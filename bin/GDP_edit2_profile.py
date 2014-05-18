import pynfg as pynfg
import numpy as np
from itertools import product
from framework_edit2 import Flight, Airline



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



# a = Flight(10, 'sw', 25, 100)
# b = Flight( 11, 'sw', 12, 120)
# c = Flight(12, 'at', 9, 90)
# d = Flight(13, 'at', 19, 66)
# net = build_net([a,b,c,d], [14, 16])







