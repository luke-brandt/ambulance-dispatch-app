import csv
import os
import time
import networkx as nx

### Load the CSV FILES

def load_csv(filename):
    data = []
    with open(filename, newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            data.append(row)
        return data

ambulances = load_csv("../ambulance.csv")
call_priority = load_csv("../call_priority.csv")
calls = load_csv("../calls.csv")
location_networks = load_csv("../location_network.csv")


### Create a priority lookup dictionary
priority_lookup = {}

for priority_row in call_priority:
    call_type = priority_row['Call Type']
    priority_number = int(priority_row["Priority"])

    priority_lookup[call_type] = priority_number

### Add priority number to each call
for call in calls:
    call_type = call["Call Type"]

    call['Priority'] = priority_lookup[call_type]


### Sort calls by priority
calls.sort(
    key=lambda call: call["Priority"]
)


### Build network graph
network_graph = nx.DiGraph()

for location in location_networks:
    origin = location["Start"]
    destination = location["End"]

    ## Apply delay time to the travel time.
    travel_time = float(location["Travel Time"])
    delay = float(location["Traffic Delay"])

    total_travel_time = travel_time + delay

    network_graph.add_edge(origin, destination, weight=total_travel_time)


### Function for running Floyd Warshall algorithm
def find_fastest_route(network_graph, start_dispatch, end_dispatch, verbose=False):
    try:
        predecessors, distances = nx.floyd_warshall_predecessor_and_distance(
            network_graph, weight="weight"
        )


        ### If the the starting location is the same as the end set the path to the starting location
        if start_dispatch == end_dispatch:
            path = [start_dispatch]
        else:
            path = nx.reconstruct_path(start_dispatch, end_dispatch, predecessors)

        total_time = distances[start_dispatch][end_dispatch]


        if verbose:
            print(f"Path found: {' -> '.join(path)}")
            print(f"Total time: {total_time} minutes")

    #Return if there is no path
    except nx.NetworkXNoPath:
        total_time = float("inf")
        path = []
    #Return if the start or end node is not in the graph
    except nx.NodeNotFound:
        total_time = float("inf")
        path = []

    return total_time, path



def print_summary_table(dispatch_results):

    headers = ["Call ID", "Call Type", "Call Location", "Ambulance Assigned", "Route to Call Location", "Time to the Call Location", "Search Time"]
    rows = []

    for entry in dispatch_results:
        id = f"Call ID {entry['Call ID']}"
        call_type = entry['Call Type']
        call_location = entry['Call Location']
        amb = entry['Ambulance Assigned']
        route = " --> ".join(entry['Route to Call Location'])
        time =  f"{entry['Time to the Call Location']} min"
        search = f"{entry['Search Time']:.4f} ms"

        rows.append([
            id,
            call_type,
            call_location,
            amb,
            route,
            time,
            search
        ])

    column_widths = []
    for col_index, header in enumerate(headers):
        longest_value = len(header)

        for row in rows:
            longest_value = max(longest_value, len(row[col_index]))

        column_widths.append(longest_value)

    def format_row(values):
        cells = [
            value.ljust(column_widths[i]) for i, value in enumerate(values)
        ]
        return " | ".join(cells)

    divider = "-+-".join("-" * width for width in column_widths)

    print(format_row(headers))
    print(divider)

    for row in rows:
        print(format_row(row))

### Function for opening the ambulance_call_log file and appending each call record to it
def export_dispatch_results_csv(dispatch_results, filename="ambulance_call_log.csv"):

    fieldnames=[
        "call_id",
        "call_type",
        "call_location",
        "ambulance_assigned",
        "route_to_call_location",
        "time_to_the_call_locations"
    ]

    file_exists = os.path.isfile(filename)
    write_header = not file_exists or os.path.getsize(filename) == 0

    with open(filename, "a", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

        if write_header:
            writer.writeheader()

        for entry in dispatch_results:
            writer.writerow({
                "call_id": entry['Call ID'],
                "call_type": entry['Call Type'],
                "call_location": entry['Call Location'],
                "ambulance_assigned": entry['Ambulance Assigned'],
                "route_to_call_location": " --> ".join(entry['Route to Call Location']),
                "time_to_the_call_locations": f"{entry['Time to the Call Location']} min"
            })

    full_path = os.path.abspath(filename)
    # print(f"\nDispatch results appended to: {filename}")
    # print(f"Full file location: {full_path}")




## Select the next call for route planning
def find_fastest_ambo(ambulances, network_graph, end_dispatch, shortest_time, verbose):

    fastest_path = []
    temp_fastest = None

    for amb in ambulances:

        start_dispatch = amb["Staging Location"]
        if verbose:
            print("\nLooking at the next Ambulance")
            print("="*40)
            print(f"Ambulance Number: {amb['Ambulance Number']}")
            print(f"Ambulance Starting location: {start_dispatch}")


        total_time, path = find_fastest_route(network_graph, start_dispatch, end_dispatch, verbose=False)

        if verbose:
            print(f"Path traveled {path} time traveled: {total_time} min.")
            print()

            ### Store the fastest ambulance based on ambulance list, if there is a tie which ever one is called first is stored.
        if total_time < shortest_time:
            shortest_time = total_time
            fastest_path = path
            temp_fastest = amb
    return shortest_time,fastest_path,temp_fastest

def run_dispatch(ambulances, calls, network_graph, verbose):

    run_start_time = time.perf_counter()

    log_file = "ambulance_call_log.csv"
    if os.path.exists(log_file):
        os.remove(log_file)

    dispatch_results = []
    for call in calls:
        end_dispatch = call["Location"]

        if verbose:
            print("\nNEXT CALL TO ANSWER")
            print("="*40)
            print(f"Priority {call['Priority']}")
            print(f"Call ID: {call['Call ID']}")
            print(f"Call Type: {call['Call Type']}")
            print(f"Call Location: {end_dispatch}")
            print("")


        shortest_time = float("inf")
        fastest_amb = ""

        ### Start timer to calculate run time for searching through all of the ambulances
        dispatch_start_time = time.perf_counter()

        #Search through each ambulance with each call
        shortest_time, path, fastest_amb = find_fastest_ambo(ambulances, network_graph, end_dispatch, shortest_time, verbose=False)

        dispatch_end_time = time.perf_counter()

        elapsed_seconds = dispatch_end_time - dispatch_start_time
        elapsed_seconds = elapsed_seconds * 1000

        if verbose:
            print(f"Total run time {elapsed_seconds:.4f} ms")

        ### record the results for current call
        call_result = ({"Call ID": call['Call ID'],
                                 "Call Type": call['Call Type'],
                                 "Call Location": end_dispatch,
                                 "Ambulance Assigned": fastest_amb['Ambulance Number'],
                                 "Route to Call Location": path,
                                 "Time to the Call Location": shortest_time,
                                 "Search Time": elapsed_seconds})

        ### Add the current call to a call log
        export_dispatch_results_csv([call_result], filename=log_file)

        ### Add the results to a full results table
        dispatch_results.append(call_result)

        run_end_time = time.perf_counter()
        total_run_elapsed = run_end_time - run_start_time

    return dispatch_results, total_run_elapsed


print("\nSTARTING DISPATCH RUN")
print("=" * 40)
print(f"Number of Calls: {len(calls)}")
print(f"Ambulances ready: {len(ambulances)}")
print("=" * 40)
if calls:
    ### run the calls, calculate the total time it takes to find the fast ambulance for each call.
    dispatch_results, total_run_elapsed = run_dispatch(ambulances, calls, network_graph, verbose=False)
    ### Display a table of all the run results
    print("\nDISPATCH RUN SUMMARY")
    print("=" * 40)
    print_summary_table(dispatch_results)
    print()
    print(f"Ambulances dispatched: {len(dispatch_results)}")
    print(f"Total run time: {total_run_elapsed * 1000:.4f} ms "
        f"({total_run_elapsed:.6f} seconds)")
else:
    print("\nThere are currently no calls to answer.")

### Run performance test

PERFORMANCE_TEST_RUNS = 10

print("\n" + "=" * 40)
print(f"PERFORMANCE TEST ({PERFORMANCE_TEST_RUNS}) RUNS")
print("=" * 40)

runt_times_ms = []

for run_num in range(1, PERFORMANCE_TEST_RUNS + 1):
    results, run_elapsed = run_dispatch(ambulances, calls, network_graph,verbose=False)
    run_elapsed_ms = run_elapsed * 1000
    runt_times_ms.append(run_elapsed_ms)

    print(f"Run {run_num:>2}: {run_elapsed_ms:.4f} ms on {len(calls)} calls")

average_run_ms = sum(runt_times_ms) / len(runt_times_ms)
print(f"\nAverage run time: {average_run_ms:.4f} ms")
print("\n" + "=" * 40)

