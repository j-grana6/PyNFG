"""
Flight and Airline objects
"""
import numpy as np
from cvxopt import matrix, solvers
from cvxopt.glpk import ilp, options
import copy 

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
t
    """

    def __init__(self, name, flights, GDP_slots, theta_space):
        self.name = name
        self.flights = flights
        self.GDP_slots = GDP_slots
        self.theta_space = theta_space
        self.num_pass = [fl.num_passengers for fl in flights]
        self.flight_arrival_times = [fl.arr_time for fl in self.flights]
        # These are ERTA
        self.ctas = [fl.cta for fl in self.flights] #cta
        self.budget_lb = dict(zip(self.theta_space, [0]*len(self.theta_space)))
        self.budget = self._get_budget()
        self.num_pass = [fl.num_passengers for fl in flights]


    def allocate_slots_old(self, slots_awarded, theta, d_multiplier = 1, delta=.24):
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
        num_passengers = np.asarray([fl.num_passengers for fl in self.flights])
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
        #options['LPX_K_TOLOBJ']= .001
        options['LPX_K_OBJLL'] = self.budget_lb[theta]
        options['LPX_K_MIPGAP'] = .15
        options['LPX_K_TMLIM'] = 2
        mod = ilp(C, G, h, A, B, B=Binary)
        res = np.asarray(mod[1])
        al_cost = np.mat(C).T * np.asarray(res)
        num_passengers = np.tile(num_passengers, (flight_slots,1)).T.flatten()
        #  ^ Matches shape of cost vector
        social_cost = delta * np.dot(res.flatten()*((.9986 + .0132*c.T)*c.T), num_passengers)
        #social_cost =  delta * np.dot(res.flatten()*c.T, num_passengers)
        
        return np.float_(al_cost), np.float_(social_cost)


    def allocate_slots(self, slots_awarded, theta, d_multiplier = 1, delta=.24):
        """
        Solves the binary integer programming problem to best allocate
        GFP slots. It returns the total cost of the optimal allocation.

        Parameters
        ----------

        slots_awarded : list
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
        f_a_t = np.asarray(sorted(copy.deepcopy(self.flight_arrival_times)))
        s_a = np.asarray(sorted(slots_awarded))
        delay_times = []
        num_pass = []
        itest = range(len(s_a))[::-1]
        for ix in range(len(s_a))[::-1]:
            try:
                slot = s_a[ix]
                f = np.max(f_a_t[f_a_t <=slot +.1])
                delay_times.append( max(0, slot - f) )
                f_a_t = f_a_t[f_a_t != f]
                num_pass_ix = self.flight_arrival_times.index(f)
                num_pass.append(self.num_pass[num_pass_ix])
            except ValueError:
                pass #If when calculating budget, can't assign a flight
        num_cancelled = len(self.flight_arrival_times) - len(delay_times)
        
        for f in f_a_t: # Get the passengers of cancelled flights
            num_pass_ix = self.flight_arrival_times.index(f)
            num_pass.append(self.num_pass[num_pass_ix])
        delay_times.extend([theta[0]] * num_cancelled)
        dt = np.asarray(delay_times)
        dc_permin = delay_cost(dt, theta[1])
        total_dc = np.sum(dc_permin * dt)
        sc = (.0132 * dt +.9986)*dt*num_pass*delta
        return total_dc, np.sum(sc)


    def _get_budget(self):
        """ Computes the budget for airline bids

        Parameters
        ----------

        slot_times_remaning : list
            A list where each element is the post GDP slots that the airline
            can bid for.  Times are expressed as minutes after the GDP program


        """

        budget = {}
        budget_lb = {}
        for theta in self.theta_space:
            max_cost_per_min = delay_cost(np.asarray([theta[0]]), theta[1])
            # highest cost per minute is if all flights canceled
            budget_max = max_cost_per_min * theta[0]*len(self.flights)
            budget_min = self.allocate_slots(self.GDP_slots, theta)[0]
            ### To get budget min, do a linear programming problem.
            ### assume that an airline wins all slots then minimizes the cost.
            budget[theta] = np.float(budget_max-budget_min)
            budget_lb[theta] = budget_min
        self.budget = budget
        self.budget_lb = budget_lb
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
    Delay costs/min are DC/min(15) for 15<c<65
    DC/min as fitted through points in westminster for 15<m<65
    DC/min such that TC is extended linearly


    """
    
    true_delay = np.zeros(len(time_delayed)) 
    euro_to_dollar = .9916
    inflation = 1.22
    less_than_15 = time_delayed <= 15
    between_range = np.bool_(np.int_(time_delayed > 15) * np.int_(time_delayed < 65)).flatten()
    greater_than_65 = time_delayed >= 65
    if airline_type == 'low':
        true_delay[less_than_15] = .8
        true_delay[between_range] = (-9.94 + .716*time_delayed)[between_range]
        true_delay[greater_than_65] = (83.14 -3025./time_delayed)[greater_than_65]

    elif airline_type == 'base':
        true_delay[less_than_15] = 1.3
        true_delay[between_range] = (-20.75 + 1.47*time_delayed)[between_range]
        true_delay[greater_than_65] = (170.35 -6210./time_delayed)[greater_than_65]

    elif airline_type == 'high':
        true_delay[less_than_15] = 16.6
        true_delay[between_range] = (-18.05 + 2.31*time_delayed)[between_range]
        true_delay[greater_than_65] = (282.25 -9760./time_delayed)[greater_than_65]


    return true_delay * inflation * euro_to_dollar
