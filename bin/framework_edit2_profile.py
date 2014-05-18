"""
Flight and Airline objects
"""
import numpy as np
from cvxopt import matrix
from cvxopt.glpk import ilp, options


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

    def __init__(self, number, airline, arr_time, num_passengers):
        self.number = number
        self.airline = airline
        self.arr_time = arr_time
        self.num_passengers = num_passengers

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
        self.flight_arrival_times = [fl.arr_time for fl in self.flights]
        self.budget = self._get_budget()


    def allocate_slots(self, slots_awarded, theta, d_multiplier = 1, delta=1):
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
        num_passengers = np.asarray([fl.num_passengers for fl in self.flights])
        # How many slots are in the GDP
        num_slots = len(slots_awarded)
        # How many flights does the airline need to schedule
        num_flights = len(flight_arrival_times)

        # All possible allocations for a flight.  A flight can either have a
        #slot or be canceled.

        flight_slots = num_slots + num_flights
        c = []
        for elem in flight_arrival_times:
            c.append(np.concatenate(((np.asarray(slots_awarded) - elem),
                                     np.ones(len(flight_arrival_times)) *
                                     theta[0])))

            # c is the minutes late for all flights for each slot.  For example, if an
            # airline has 3 GDP slots and 5 flights, the first 8 elements
            # of c correspond to the minute delay of allocating the first
            # flight to that slot.  Each flight has its own
            # 'cancellation'  slot.  Therefore, the size of c is
            # (num_slots + num_flights)*num_flights.

        c = np.squeeze(c).flatten()
        ones_vec = np.ones(flight_slots)

        ##  G1 - Only assigns flights to slots that are after scheduled time:
        # Note that this uses c, which are times, not C which are costs.
        G1 = np.zeros((len(flight_arrival_times), len(c)))
        for fl in range(len(flight_arrival_times)):
            G1[fl, fl*len(ones_vec): (fl+1)*len(ones_vec)] = \
                c[fl*(flight_slots): (fl+1)*(flight_slots)]

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

        options['LPX_K_MSGLEV'] = 0  # TODO: Change to errors only
        mod = ilp(C, G, h, A, B, B=Binary)

        res = np.asarray(mod[1])
        al_cost = np.mat(C).T * np.asarray(res)
        num_passengers = np.tile(num_passengers, (flight_slots,1)).T.flatten()
        #  ^ Matches shape of cost vector
        social_cost =  delta * d_multiplier * np.dot(res.flatten()*c.T, num_passengers)

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

    if airline_type == 'low':
        cost =   -.10005128 * time_delayed + .01022564*time_delayed**2
    elif airline_type == 'base':
        cost =  -.2325641*time_delayed + .02128205*time_delayed**2
    elif airline_type == 'high':
        cost =  .82851282*time_delayed + .01854359*time_delayed**2

    cost[cost<0] = 0
    return cost
