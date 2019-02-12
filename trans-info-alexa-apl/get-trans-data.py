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

TABLE_NAME_DB = 'victoria-trans-info'
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

#with open('route_stops.json', 'w') as outfile:
#    json.dump(data, outfile)

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

rq = '/v3/stops/location/{0},{1}'.format(-37.824170, 145.060789)
response = requests.get(getUrl(rq ))
print(response)