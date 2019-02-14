from hashlib import sha1
import hmac
import copy
import json
import requests
from  urllib.parse import urlencode
BASE_URL = 'http://timetableapi.ptv.vic.gov.au'
devid  = 3000956
KEY = 'fc6ed54a-7866-4a71-95a2-b10d3e48777b'
TABLE_NAME_DB = 'victoria-trans-info'
bkey = bytearray(KEY, 'utf-8')
# route_types (array of integer) is required
api_get_routes = '/v3/routes'
# route id (integer) is required
api_get_route_info = '/v3/routes/{0}?'
# No parameter
api_get_route_types = '/v3/route_types'

# GET /v3/stops/route/{route_id}/route_type/{route_type}
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


def get_all_stops_of_route(route_type, route_id):
    api_query = '/v3/stops/route/{0}/route_type/{1}'.format(route_id, route_type)
    print('query for get_all_stops_of_route = {0}'.format(api_query))
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


def save_all_routes_dynamodb():
    try:
        response = requests.get(getUrl('/v3/routes')).json()['routes']
        all_routes = dict()
        client = boto3.client('dynamodb')
        all_routes['all_routes'] = response
        response = client.update_item(
            TableName=TABLE_NAME_DB,
            Key={'data_type': {'S': 'all_routes'},
                 },
            AttributeUpdates={'data_value': {
                'Value': {'S': json.dumps(all_routes['all_routes'])}
            }, }
        )
    except:
        print("Source:save_all_routes_dynamodb, Error while saving data from DynamoDB")


"""
Read data_value from dynamoDB
"""
def get_item_from_dynamodb(key_name):
    try:
        client = boto3.client('dynamodb')
        response = client.get_item(
            Key={
                'data_type': {
                    'S': key_name,
                },
            },
            TableName=TABLE_NAME_DB,
        )
        routes_list = json.loads(response['Item']['data_value']['S'])
        return routes_list
    except:
        print("Source:get_all_routes_from_dynamodb, Error while reading data from DynamoDB")
        return None

def get_url_encode_manually(input:str):
    input = input.replace(" ", "%20")
    input = input.replace("#", "%23")
    input = input.replace("-", "%2D")
    input = input.replace("&", "%26")
    input = input.replace("!", "%21")
    input = input.replace("'", "%27")
    input = input.replace("(", "%28")
    input = input.replace(")", "%29")
    input = input.replace("+", "%2B")
    input = input.replace("-", "%2D")
    input = input.replace(".", "%2E")
    input = input.replace("/", "%2F")
    return input

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



import  boto3
# rts = None
# response = requests.get(getUrl('/v3/routes')).json()['routes']
# all_routes = dict()
# client = boto3.client('dynamodb')
# all_routes['all_routes'] = response
# response = client.update_item(
#     TableName='victoria-trans-info',
#     Key={'data_type': {'S': 'all_routes'},
#          },
#     AttributeUpdates={'data_value': {
#         'Value': {'S': json.dumps(all_routes['all_routes'])}
#     }, }
# )
#
# print(response)
#
# response = client.get_item(
#     Key={
#         'data_type': {
#             'S': 'all_routes',
#         },
#
#     },
#     TableName='victoria-trans-info',
# )
# routes_list = json.loads(response['Item']['data_value']['S'])
# for r in routes_list:
#     print(r['route_name'])


#route_stops = get_item_from_dynamodb('route_stops')['route_stops']
# -37.824170, 145.060789
route_type = 2
import  re
search_term = 'Collinson St/Fullarton Rd '
search_term = re.sub('[^A-Za-z0-9]+', ' ', search_term)
search_term = search_term.strip(' ').split(' ')[0]

#search_term = search_term.replace(" ", '%20')
#param_query = '/v3/search/{0}?route_types={1}&include_addresses=false&include_outlets=false&match_route_by_suburb=false&match_stop_by_gtfs_stop_id=false'.format(
#    search_term , route_type)
#res = requests.get(getUrl(param_query))
address = 'C-104, Renaissance Prospero,BYatarayanapura, Bangalore 560092,India'
param = urlencode({'address': address, 'key': 'AIzaSyDKfFQStruF8z9wuvuTiv_74OL-vaC0cIU'})
#query = 'https://maps.googleapis.com/maps/api/geocode/json?' + param
response = requests.get('https://maps.googleapis.com/maps/api/geocode/json?', param).json()
print(response)
lat_long = [-37.824170, 145.060789]
response = requests.get(getUrl('/v3/stops/location/{0},{1}'.format(lat_long[0], lat_long[1])))
print(response.json())