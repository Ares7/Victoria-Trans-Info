from hashlib import sha1
import hmac
import copy
import json
import requests
from  urllib.parse import urlencode
BASE_URL = 'http://timetableapi.ptv.vic.gov.au'
devid  = 3000956
KEY = 'fc6ed54a-7866-4a71-95a2-b10d3e48777b'
bkey = bytearray(KEY, 'utf-8')
# route_types (array of integer) is required
api_get_routes = '/v3/routes'
# route id (integer) is required
api_get_route_info = '/v3/routes/{0}?'
# No parmaeter
api_get_route_types = '/v3/route_types'

#GET /v3/stops/route/{route_id}/route_type/{route_type}
api_get_stops_on_route = '/v3/stops/route/{0}/route_type/{1}'



def getUrl(request):
    request = request + ('&' if ('?' in request) else '?')
    raw = request + 'devid={0}'.format(devid)
    hashed = hmac.new(bkey, raw.encode('utf-8'), sha1)
    signature = hashed.hexdigest()
    return BASE_URL + raw + '&signature={1}'.format(devid, signature)

def get_all_sotps_of_route(route_type, route_id):
    api_query = '/v3/stops/route/{0}/route_type/{1}'.format(route_id, route_type)
    response = requests.get(getUrl(api_query))
    stop_name_id_dict = dict()
    if response.status_code == 200:
        stops_list = response.json()['stops']
        for i in range(len(stops_list)):
            stop_name_id_dict[stops_list[i]['stop_name']] = stops_list[i]['stop_id']
        return stop_name_id_dict
    else:
        print('response code = {0} , problem in getting stop for the route'.format(response.status_code))
        return None
#param = urlencode({'route_types':[3]})
#response = requests.get(getUrl('/v3/routes?' + param ))

#response = requests.get(getUrl('/v3/routes' ))
#response = requests.get('http://timetableapi.ptv.vic.gov.au/v3/routes?devid=3000956&signature=D1567E907B2147F84EC62BC8D79E7EBE3795EB83')
#status_code = response.status_code
def get_all_sotps_of_route(route_type, route_id):

    api_query = '/v3/stops/route/{0}/route_type/{1}'.format(route_id, route_type)
    response = requests.get(getUrl(api_query))
    stop_name_id_dict = dict()
    if response.status_code == 200:
        stops_list = response.json()['stops']
        for i in range(len(stops_list)):
            stop_name_id_dict[stops_list[i]['stop_name']] = stops_list[i]['stop_id']
        return stop_name_id_dict
    else:
        print('response code = {0} route_type = {1} route_id ={2} problem in getting stop for the route'.format(
            response.status_code, route_type, route_id))
        return None


def get_line_names():
    param = urlencode({'route_types': [0]})
    response = requests.get(getUrl('/v3/routes?' + param))
    routes = list()
    routes_name_id_map = dict()
    if response.status_code == 200:
        for item in response.json()['routes']:
            routes.append(item['route_name'])
            routes_name_id_map[item['route_name']] = item['route_id']
        return [routes, routes_name_id_map]
    else:
        return None


def get_route_types() -> list:
    response = requests.get(getUrl('/v3/route_types'))
    routes_type_names = list()
    routes_name_type_map = dict()
    if response.status_code == 200:
        for item in response.json()['route_types']:
            routes_type_names.append(item['route_type_name'])
            routes_name_type_map[str.lower(item['route_type_name'])] = item['route_type']
        return [routes_type_names, routes_name_type_map]
    else:
        return None


def get_stop_id_in_mode(stop_name:str, route_type:int, route_id:int) -> list:
    print('entered in get_stop_id_in_mode for stop_name = {0} route_type = {1} route_id = {2}'.format(stop_name, route_type, route_id))
    stop_name_ids = get_all_sotps_of_route(route_type, route_id)
    print('stop name id pair ={0}'.format(stop_name_ids))
    if stop_name_ids is not None:
        st_list = copy.deepcopy(list(stop_name_ids.keys()))
        # try exact match first
        for st in st_list:
            if stop_name == st:
                return [st, stop_name_ids[st]]
        # try partial first match
        for st in st_list:
            if stop_name in st:
                return [st, stop_name_ids[st]]
    return None



#all_routes = requests.get(getUrl('/v3/routes' )).json()['routes']

# for r in all_routes:
#     route_type =  r['route_type']
#     route_id  =   r['route_id']
#     route_name =  r['route_name']
#     route_number = r['route_number']
#
#
#     api_query = '/v3/stops/route/{0}/route_type/{1}'.format(route_id , route_type)
#     res = requests.get(getUrl(api_query)).json()
#     stops_of_route = res['stops']
#     for i in range(len(stops_of_route)):
#
#         stop_data_item['route_type'] = route_type
#         stop_data_item['route_id']   = route_id
#         stop_data_item['route_name'] = route_name
#         stop_data_item['route_number'] = route_number
#         stop_data_item['route_type'] = route_type
#         stop_data_item['disruption_ids'] = stops_of_route[i]['disruption_ids']
#         stop_data_item['stop_name']= stops_of_route[i]['stop_name']
#         stop_data_item['stop_id']= stops_of_route[i]['stop_id']
#         stop_data_item['stop_latitude'] = stops_of_route[i]['stop_latitude']
#         stop_data_item['stop_longitude'] = stops_of_route[i]['stop_longitude']
#
#
#         stop_data.append( stop_data_item)
#         break
#     break
# with open('data.txt', 'w') as f:
#   json.dump(stop_data, f, ensure_ascii=False)
# {
#       "stop_id": 1002,
#       "route_id": 1,
#       "run_id": 950374,
#       "direction_id": 1,
#       "disruption_ids": [],
#       "scheduled_departure_utc": "2019-01-22T13:14:00Z",
#       "estimated_departure_utc": null,
#       "at_platform": false,
#       "platform_number": "1",
#       "flags": "",
#       "departure_sequence": 0
#     },

# get route name from route_id
def get_route_name(route_id):
    api_query = '/v3/routes/{0}'.format(route_id)
    res = requests.get(getUrl(api_query))
    if res.status_code == 200:
        res = res.json()
        if res.get('route') is not None:
            return  res['route']['route_name']

    return None

# get direction from direction id
def get_direction_name(route_id, direction_id):
    try:
        api_query = '/v3/directions/route/{0}'.format(route_id)
        res = requests.get(getUrl(api_query))
        if res.status_code == 200:
            for dir in res.json()['directions']:
                # to be on safer side
                if str(dir['direction_id']) ==  str(direction_id):
                    dir_name = dir['direction_name'].replace("(", "")
                    dir_name = dir_name.replace(")", "")

                    return dir_name
    except Exception as ex:
        print('error {0} while getting direction name for route_id = {1} and direction_id = {2}'.format(ex.args[0], direction_id))
    return None

# get 5 departures
def get_departures_for_mode_and_stop(route_type, search_term):
    search_term = search_term.replace(' ', '%20')
    param_query = '/v3/search/{0}?route_types={1}&include_addresses=false&include_outlets=false&match_route_by_suburb=false&match_stop_by_gtfs_stop_id=false'.format(search_term,route_type)
    res = requests.get(getUrl(param_query)).json()
    print(res)
    i=0
    dep_list = list()
    if res.get('stops') is not None:
        for stop in res.get('stops'):
            stop_id  = stop['stop_id']
            stop_name = stop['stop_name']
            api_query = '/v3/departures/route_type/{0}/stop/{1}'.format(route_type, stop_id)
            res_dep = requests.get(getUrl(api_query)).json()['departures']
            for dep in res_dep:
                dep_platform_number = dep['platform_number']
                dep_route_name = get_route_name(dep['route_id'])
                route_name = dep_route_name if dep_route_name is not None else "Not Available"
                dep_direction_id = get_direction_name(dep['route_id'], dep['direction_id'])
                dep_direction_id = dep['direction_id'] if dep_direction_id is None else dep_direction_id
                i = i + 1
                dep_list.append({
                    'stop_name':stop_name,
                    'route_name': route_name,
                    'direction': dep_direction_id,
                    'scheduled_departure_utc': dep['scheduled_departure_utc'],
                    'platform_number': dep_platform_number
                })
                print(i)
                if i == 5:
                    return dep_list


    return None



# get 5 departures
def get_facility_for_stop(search_term):
    orig_search_term = search_term
    search_term = search_term.replace(' ', '%20')
    param_query = '/v3/search/{0}?route_types=0&route_types=3&include_addresses=false&include_outlets=false&match_route_by_suburb=false&match_stop_by_gtfs_stop_id=false'.format(search_term)
    res = requests.get(getUrl(param_query)).json()
    i=0
    dep_list = list()
    stop_descr_available = True
    speech_text = ""
    if res.get('stops') is not None:
        stop = res.get('stops')[0]
        stop_id  = stop['stop_id']
        stop_name = stop['stop_name']
        stop_route_type = stop['route_type']
        api_query = '/v3/stops/{0}/route_type/{1}'.format(stop_id,stop_route_type)
        resp = requests.get(getUrl(api_query)).json()
        resp_facility = resp['stop']
        stop_descr = resp_facility['station_description']
        if (stop_descr is None or stop_descr == "")== False:
            speech_text = 'At stop {0}  {1}'.format(stop_name, stop_descr)
            stop_amenities  = resp_facility['stop_amenities']
            if stop_amenities is not None:
                try:
                    if str(stop_amenities['toilet']) in ['True', 'true']:
                        speech_text = speech_text + 'Toilet is available'
                    else:
                        speech_text = speech_text + 'Toilet is  not available'
                    if stop_amenities is not None:
                        if str(stop_amenities['taxi_rank']) in ['True', 'true']:
                            speech_text = speech_text + 'taxi rank is available'
                        else:
                            speech_text = speech_text + 'taxi rank is  not available'
                    if stop_amenities is not None:
                        if stop_amenities['car_parking'] is not None:
                            speech_text = speech_text + 'car parking is {0}'.format(stop_amenities['car_parking'])
                        else:
                            speech_text = speech_text + 'car parking is not available'
                except Exception as ex:
                    print('Got error while fetching facilities for stop. {0}'.format(ex.args[0]))

        else:
            speech_text = 'Sorry, for stop {0}  information is not available. Please try later'.format(stop_name)

        if speech_text == "":
            speech_text = 'Sorry no information found for the stop'
    else:
        speech_text = 'Sorry no stop found for the input'

    speech_text = speech_text.replace('/', ' ')

    return speech_text




search_term = 'Casterton'
route_type = 0
# departure_list = get_departures_for_mode_and_stop(route_type, search_term)
# if departure_list is not None:
#     speech_text = 'At stop {0}, next {1} departures are  '.format(departure_list[0]['stop_name'], len(departure_list))
#     speech = list()
#     for i in range(len(departure_list)):
#         time = departure_list[i]['scheduled_departure_utc'].split('T')[1].replace('Z','') + ' UTC'
#         speech.append('At {0} for route {1} in direction {2} at platform number {3} '.format(
#             time, departure_list[i]['route_name'], departure_list[i]['direction'],
#             departure_list[i]['platform_number'])
#         )
#
#     speech_text = speech_text + ", ".join(speech)
#     print(speech_text)
#response1 = requests.get(getUrl('/v3/stops/route/1/route_type/0')).json()
# "route": {
#     "route_type": 0,
#     "route_id": 0,
#     "route_name": "string",
#     "route_number": "string",
#     "route_gtfs_id": "string"
# },
response = requests.get(getUrl('/v3/routes')).json()['routes']
all_routes = dict()
all_routes['all_routes']=response
with open('all_routes_list.json', 'w') as outfile:
    json.dump(all_routes, outfile)


def get_all_routes(route_type:int):
    routes = list()
    try:
        try:
            with open('all_routes_list.json') as f:
                data = json.load(f)['all_routes']
                routes = [rt for rt in data if rt['route_type'] == route_type]
        except:
            print('Source: get_all_routes error while reading route from file')
        if len(routes) < 1:
            response = requests.get(getUrl('/v3/routes')).json()['routes']
            routes = [rt for rt in response if rt['route_type'] == route_type]

    except:
        print('Source: get_all_routes, error while getting all routes:')
    return routes

stop_name_id_pair = get_all_sotps_of_route(2,954)
data = dict()
data["route_type"] = 2
data["route_id"] = 954
#data["route_stops"] = [{v:k } for k, v in stop_name_id_pair.items()]
data["route_stops"] =  stop_name_id_pair

with open('route_stops.json', 'w') as outfile:
    json.dump(data, outfile)
