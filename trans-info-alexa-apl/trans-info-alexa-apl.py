import os
import json
import copy
import re
from ask_sdk_core.skill_builder import CustomSkillBuilder
from ask_sdk_core.api_client import DefaultApiClient
from ask_sdk_core.utils import is_request_type
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_model.interfaces.alexa.presentation.apl import UserEvent
from ask_sdk_model.dialog.delegate_directive import DelegateDirective
from ask_sdk_model.interfaces.alexa.presentation.apl import RenderDocumentDirective
from ask_sdk_model.response import Response
from ask_sdk_model.ui import AskForPermissionsConsentCard
from ask_sdk_model.services import ServiceException
from ask_sdk_core.utils import is_intent_name
import boto3
from hashlib import sha1
import hmac
import requests
from urllib.parse import urlencode
from ask_sdk_dynamodb.adapter import DynamoDbAdapter
TABLE_NAME_DB = 'victoria-trans-info'
sb = CustomSkillBuilder(api_client=DefaultApiClient(),
                        persistence_adapter=DynamoDbAdapter(table_name=TABLE_NAME_DB,
                                                            partition_key_name='data_type',
                                                            attribute_name='data_value',
                                                            create_table=False))

BASE_URL = 'http://timetableapi.ptv.vic.gov.au'
# route_types (array of integer) is required
api_get_routes = '/v3/routes?'
# route id (integer) is required
api_get_route_info = '/v3/routes/%5B0%5D?'
# No parmaeter
api_get_route_types = '/v3/route_types'
# GET /v3/stops/route/{route_id}/route_type/{route_type}
api_get_stops_on_route = '/v3/stops/route/{0}/route_type/{1}'

# /v3/stops/route/{route_id}/route_type/{route_type}
api_get_route_stops = '/v3/stops/route/{0}/route_type/{1}'

api_get_nearby_stops = '/v3/stops/location/{0},{1}'

PTV_API_KEY = os.environ['PTV_API_KEY']
PTV_DEV_ID = os.environ['PTV_DEV_ID']

GEO_LOCATION_API_KEY = os.environ['GEO_LOCATION_API_KEY']

MODE_IMAGE_DICT = {'train': 'https://s3.amazonaws.com/aws-apl-contest/transInfo/logo/train_hi_res_512.png',
                   'bus': 'https://s3.amazonaws.com/aws-apl-contest/transInfo/logo/bus_hi_res_512.png',
                   'tram': 'https://s3.amazonaws.com/aws-apl-contest/transInfo/logo/tramhi_res_512.png',
                   'vline': 'https://s3.amazonaws.com/aws-apl-contest/transInfo/logo/vline.png',
                   'night bus': 'https://s3.amazonaws.com/aws-apl-contest/transInfo/logo/nightbus_hi_res_512.png'}
NOTIFY_MISSING_PERMISSIONS = ("Please enable Location permissions in the Amazon Alexa app.")
NO_ADDRESS = ("It looks like you don't have an address set. You can set your address from the companion app.")
ADDRESS_AVAILABLE = "Here is your full address: {}, {}, {}"
ERROR = "Uh Oh. Looks like something went wrong."
LOCATION_FAILURE = ("There was an error with the Device Address API. Please try again.")
LAUNCH_TEXT = "Welcome, ask trans info about routes, nearby stops and departures for Public Transport Victoria." +\
                  " You can say get departures"

permissions = ["read::alexa:device:all:address"]

def getUrl(request):
    request = request + ('&' if ('?' in request) else '?')
    raw = request + 'devid={0}'.format(PTV_DEV_ID)
    bkey = bytearray(PTV_API_KEY, 'utf-8')
    hashed = hmac.new(bkey, raw.encode('utf-8'), sha1)
    signature = hashed.hexdigest()
    return BASE_URL + raw + '&signature={1}'.format(PTV_DEV_ID, signature)


def is_apl_supported(handler_input):
    if handler_input.request_envelope.context.system.device.supported_interfaces.alexa_presentation_apl is None:
        return False
    else:
        return True


def load_apl_document(file_path):
    # type: (str) -> Dict[str, Any]
    """Load the apl json document at the path into a dict object."""
    with open(file_path) as f:
        return json.load(f)


def get_all_routes(route_type:int):
    routes = list()
    try:
        try:
            data = get_item_from_dynamodb('all_routes')
            routes = [rt for rt in data if rt['route_type'] == route_type]
            print('successfully reads routes from dynamoDB = {0}'.format(routes))
        except:
            print('Source: get_all_routes error while reading route from file')
        if len(routes) < 1:
            response = requests.get(getUrl('/v3/routes')).json()['routes']
            routes = [rt for rt in response if rt['route_type'] == route_type]

    except:
        print('Source: get_all_routes, error while getting all routes:')
    return routes


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


def get_route_types_list() -> list:
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


def get_mode_name(route_type:int):
    try:
        route_types = get_item_from_dynamodb('route_types')
        for k, v in route_types.items():
            if v == route_type:
                return k
    except Exception as ex:
        print('error source:get_route_name,  error = {0}'.format(ex.args[0]))
        return ""


def get_stop_id_in_mode(stop_name: str, route_type: int, route_id: int) -> list:
    print('entered in get_stop_id_in_mode for stop_name = {0} route_type = {1} route_id = {2}'.format(stop_name,
                                                                                                      route_type,
                                                                                                      route_id))
    stop_name_ids = get_all_stops_of_route(route_type, route_id)
    print('stop name id pair ={0}'.format(stop_name_ids))
    if stop_name_ids is not None:
        st_list = copy.deepcopy(list(stop_name_ids.keys()))
        # try exact match first
        print('stop name list {0}'.format(st_list))
        for st in st_list:
            if str.lower(stop_name) == str.lower(st):
                return [st, stop_name_ids[st]]
        # try partial first match
        for st in st_list:
            if stop_name.lower() in st.lower():
                return [st, stop_name_ids[st]]
    return None


def get_route_name(route_id):
    api_query = '/v3/routes/{0}'.format(route_id)
    res = requests.get(getUrl(api_query))
    if res.status_code == 200:
        res = res.json()
        if res.get('route') is not None:
            return res['route']['route_name']

    return None

def get_route_type(route_type_name:str):
    # note that data is stored in lower case
    route_type_dict = get_item_from_dynamodb('route_types')
    return route_type_dict[str.lower(route_type_name)]

# get direction from direction id
def get_direction_name(route_id, direction_id):
    try:
        api_query = '/v3/directions/route/{0}'.format(route_id)
        res = requests.get(getUrl(api_query))
        if res.status_code == 200:
            for dir in res.json()['directions']:
                # to be on safer side
                if str(dir['direction_id']) == str(direction_id):
                    dir_name = dir['direction_name'].replace("(", "")
                    dir_name = dir_name.replace(")", "")

                    return dir_name
    except Exception as ex:
        print('error {0} while getting direction name for route_id = {1} and direction_id = {2}'.format(ex.args[0],
                                                                                                        direction_id))
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


# get 5 departures
def get_departures_for_mode_and_stop(handler_input, route_type:int, route_type_name:str, search_term:str):
    search_modified = re.sub('[^A-Za-z0-9]+', ' ', search_term)
    search_modified = search_modified.strip(' ').split(' ')[0]
    param_query = '/v3/search/{0}?route_types={1}&include_addresses=false&include_outlets=false&match_route_by_suburb=false&match_stop_by_gtfs_stop_id=false'.format(
        search_modified, route_type)
    print('param query = {0}'.format(param_query))
    param_query = getUrl(param_query)
    print('param query = {0}'.format(param_query))
    res = requests.get(param_query).json()
    apl_doc = load_apl_document('apl_trans_info_departures.json')['document']
    apl_data = load_apl_document('apl_trans_info_departures.json')['datasources']

    i = 0
    dep_list = list()
    if res.get('stops') is not None:
        stop_id = res['stops'][0]['stop_id']
        stop_name = res['stops'][0]['stop_name']
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
                'stop_name': stop_name,
                'route_name': route_name,
                'direction': dep_direction_id,
                'scheduled_departure_utc': dep['scheduled_departure_utc'],
                'platform_number': dep_platform_number
            })
            print(i)
            if i == 5:
                break
        if len(dep_list) > 0:
            # if MODE_IMAGE_DICT.get(route_type.lower()) is not None:
                # apl_data['bodyTemplate2Data']['image'] = MODE_IMAGE_DICT.get(route_type.lower())
            apl_data['bodyTemplate2Data']['textContent']['title']['text'] = stop_name
            apl_data['bodyTemplate2Data']['textContent']['subtitle']['text'] = 'Mode: {0}'.format(route_type_name)

            speech_text = 'At stop {0}, next {1} departures for {2} are  '.format(stop_name, len(dep_list),route_type_name)
            speech = list()
            display_text = list()
            for i in range(len(dep_list)):
                time = dep_list[i]['scheduled_departure_utc'].split('T')[1].replace('Z', '') + ' UTC'
                rt = dep_list[i]['route_name']
                dr = dep_list[i]['direction']
                pt = 'Not Available' if dep_list[i]['platform_number'] in [None, 'None'] else dep_list[i]['platform_number']

                speech.append('At {0} for route {1} in direction {2} at platform number {3} '.format(time, rt, dr, pt))
                display_text = "{0}. Time: {1}  Route: {2}  Direction: {3} Platform: {4}".format(
                    i + 1, time, rt, dr, pt)
                apl_data['bodyTemplate2Data']['textContent']['primaryText' + str(i + 1)]['text'] = display_text

            speech_text = speech_text + ", ".join(speech)
            # apl_data['bodyTemplate2Data']['textContent']['primaryText']['text'] = "\n\n".join(display_text)


    else:
        speech_text = "Sorry, I could not find the information for {0}.Please try again".format(search_term)
        apl_data['bodyTemplate2Data']['textContent']['title']['text'] = search_term
        apl_data['bodyTemplate2Data']['textContent']['subtitle']['text'] = 'Mode: {0}'.format(route_type_name)
        apl_data['bodyTemplate2Data']['textContent']['primaryText1']['text'] = speech_text
        handler_input.response_builder.speak(speech_text).set_should_end_session(True)

    if is_apl_supported(handler_input):
        handler_input.response_builder.speak(speech_text).set_should_end_session(True).add_directive(
            RenderDocumentDirective(
                token="GetDepartures",
                document=apl_doc,
                datasources=apl_data
            )
        )
    else:
        handler_input.response_builder.speak(speech_text).set_should_end_session(True)

    return handler_input


def fill_routes(handler_input, mode_value, start_index=0):
    handler_input.attributes_manager.session_attributes['current_mode'] = mode_value
    ask_text = "Please say yes to know more else say No"

    all_routes = list()

    if get_route_type(str.lower(mode_value)) is not None:
        route_type = get_route_type(str.lower(mode_value))
        all_routes = get_all_routes(route_type)
        list_doc = load_apl_document('apl_route_list.json')
        data_source = list_doc['datasources']
        data_source['listTemplate1Metadata']['title'] = "Route List for {0}".format(mode_value)
        route_list = list()
        # for item in all_routes:
        #     current_route_names_list.append(item['route_name'])
        #     routes_name_id_map[item['route_name']] = item['route_id']

        i = int()
        max_index = len(all_routes) if len(all_routes) < start_index + 5 else start_index + 5
        speech_text_temp = ""
        for i in range(start_index, max_index):
            item = all_routes[i]['route_name']
            print(item)
            route_list_item = copy.deepcopy(load_apl_document('apl_route_list_item_template.json'))
            route_list_item['ordinal'] = i + 1
            route_list_item['textContent']['primaryText']['text'] = item
            route_list_item['textContent']['ecoSpotText']['text'] = item[:30] + "..." if len(item) > 33 else item
            route_list_item['listItemIdentifier'] = all_routes[i]['route_id']
            route_list_item['token'] = mode_value
            route_list.append(route_list_item)
            if i == start_index:
                speech_text_temp = item
            else:
                speech_text_temp = speech_text_temp + ",  " + item

        speech_text_temp = speech_text_temp.replace("&", "and")
        speech_text_temp = speech_text_temp.replace("-", " ")
        handler_input.attributes_manager.session_attributes['current_index'] = max_index
        data_source['listTemplate1ListData']['listPage']['listItems'] = route_list
        if start_index == 0:
            speech_text = 'Total {0} routes available for {1} and some of these are {2} '.format(
                len(all_routes), mode_value, speech_text_temp)
        else:
            speech_text = 'routes are {0} '.format(speech_text_temp)

        if max_index < len(all_routes):
            speech_text = speech_text + " Do you want to know more routes?"
            if is_apl_supported(handler_input):
                handler_input.response_builder.speak(speech_text).ask(ask_text).set_should_end_session(False).add_directive(
                    RenderDocumentDirective(
                        token="FIndRoutes",
                        document=list_doc['document'],
                        datasources=data_source))
            else:
                handler_input.response_builder.speak(speech_text).ask(ask_text).set_should_end_session(False)
        else:
            speech_text = speech_text + " To know stops of a route please say get stops? else say stop?"
            if is_apl_supported(handler_input):
                handler_input.response_builder.speak(speech_text).ask(
                    " To know stops of a route please say get stops? else say no?").set_should_end_session(
                    False).add_directive(
                    RenderDocumentDirective(
                        token="FIndRoutes",
                        document=list_doc['document'],
                        datasources=data_source))
            else:
                handler_input.response_builder.speak(speech_text).ask(ask_text).set_should_end_session(False)
    return


"""
get facilities for a station based on the search query. first search for stop in Train and then search stop in
VLine
"""


def get_facility_for_stop(handler_input, search_term, apl_template):

    search_modified = re.sub('[^A-Za-z0-9]+', ' ', search_term)
    search_modified = search_modified.strip(' ').split(' ')[0]
    param_query = '/v3/search/{0}?route_types=0&route_types=3&include_addresses=false&include_outlets=false&match_route_by_suburb=false&match_stop_by_gtfs_stop_id=false'.format(
        search_term)
    res = requests.get(getUrl(param_query)).json()
    print('search result = {0}'.format(res))
    speech_text = "Sorry, information found for the input. Please try later"
    apl_doc = load_apl_document(apl_template)['document']
    apl_data = load_apl_document(apl_template)['datasources']
    if res.get('stops') is not None:
        stop = res.get('stops')[0]
        stop_id = stop['stop_id']
        stop_name = stop['stop_name']
        stop_route_type = stop['route_type']
        apl_data['bodyTemplate2Data']['textContent']['title']['text'] = stop_name
        api_query = '/v3/stops/{0}/route_type/{1}'.format(stop_id, stop_route_type)
        resp = requests.get(getUrl(api_query)).json()
        resp_facility = resp['stop']
        stop_descr = resp_facility['station_description']
        if stop_descr not in [None, ""]:
            speech_text = 'At stop {0}  {1}'.format(stop_name, stop_descr)
            stop_amenities = resp_facility['stop_amenities']
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
            speech_text = 'Sorry, no information found for the stop'
    else:
        speech_text = 'Sorry, no stop found for the input'
        # display search term if not stop found
        apl_data['bodyTemplate2Data']['textContent']['title']['text'] = search_term

    speech_text = speech_text.replace('/', ' ')
    speech_text = re.sub('[^A-Za-z0-9,.]+', ' ', speech_text)

    apl_data['bodyTemplate2Data']['textContent']['primaryText']['text'] = speech_text

    if is_apl_supported(handler_input):
        handler_input.response_builder.speak(speech_text).set_should_end_session(True).add_directive(
            RenderDocumentDirective(
                token="GetStopInfoIntent",
                document=apl_doc,
                datasources=apl_data
            ))
    else:
        handler_input.response_builder.speak(speech_text).set_should_end_session(True)

    return


def fill_stops_list(handler_input, stop_name_dict, route_name, start_index=0):
    stops_names = list()
    stop_list = list()
    speech_text = "Sorry, Could not find the stop names for given input. Please try again"
    apl_doc = load_apl_document("apl_stop_list.json")['document']
    data_source = load_apl_document("apl_stop_list.json")['datasources']
    print('message from fill_stops_list stop_name_dict= {0}, route)name= {1} , start_index = {2} '.format(stop_name_dict, route_name, start_index))
    max_index = len(stop_name_dict.keys()) if len(stop_name_dict.keys()) < start_index + 5 else start_index + 5
    if stop_name_dict is not None:
        st_list = list(stop_name_dict.keys())
        data_source['listTemplate1Metadata']['title'] = "Stop List for Route: {0}".format(route_name)
        for i in range(start_index, max_index):
            stops_names.append(st_list[i])
            stop_list_item = copy.deepcopy(load_apl_document('apl_stop_list_item_template.json'))
            stop_list_item['ordinalNumber'] = i + 1
            stop_list_item['textContent']['primaryText']['text'] = st_list[i]
            stop_list_item['textContent']['ecoSpotText']['text'] = st_list[i][:30] + "..." if len(st_list[i]) > 33 else \
            st_list[i]
            stop_list_item['listItemIdentifier'] = st_list[i]
            stop_list_item['token'] = route_name
            stop_list.append(stop_list_item)

        # store index value in session attributes for paging
        handler_input.attributes_manager.session_attributes['current_index'] = max_index
        data_source['listTemplate1ListData']['listPage']['listItems'] = stop_list
        if start_index == 0:
            speech_text = str.format('Total {0} stops for route ' + route_name , str(len(stop_name_dict)))
        else:
            speech_text = ""

        speech_text = speech_text + ' stop names are {0}'.format(", ".join(stops_names))
        speech_text = speech_text.replace("&", "and")
        speech_text = speech_text.replace("-", " ")

    if max_index < len(stop_name_dict.keys()):
        speech_text = speech_text + " Do you want to know more stops? "
        if is_apl_supported(handler_input):
            handler_input.response_builder.speak(speech_text).ask(speech_text).set_should_end_session(False).add_directive(
                RenderDocumentDirective(token="FIndStops", document=apl_doc, datasources=data_source))
        else:
            handler_input.response_builder.speak(speech_text).ask(speech_text).set_should_end_session(False)
    else:
        speech_text = speech_text + " To know about stop info you can say get stop info? or say stop"
        if is_apl_supported(handler_input):
            handler_input.response_builder.speak(speech_text).ask(speech_text).set_should_end_session(False).add_directive(
                RenderDocumentDirective(token="FIndStops", document=apl_doc, datasources=data_source))
        else:
            handler_input.response_builder.speak(speech_text).ask(speech_text).set_should_end_session(False)

    return


def go_home_handler(handler_input, speech_text, end_session: bool):
    handler_input.response_builder.speak(speech_text).set_should_end_session(end_session)
    if is_apl_supported(handler_input):
        handler_input.response_builder.add_directive(
            RenderDocumentDirective(
                token="LaunchRequest",
                document=load_apl_document("apl_launch_trans_info.json")['document'],
                datasources=load_apl_document("apl_launch_trans_info.json")['datasources'])
        )


"""
Save all routes to daynamo db table
"""
def save_all_routes_dynamodb(handler_input):
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

    except Exception as ex:
        print("Source:save_all_routes_dynamodb, Error while saving data from DynamoDB = {0}".format(ex.args[0]))


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


def get_nearby_stop(handler_input):
    # type: (HandlerInput) -> Response
    print('message from function get_nearby_stop')
    req_envelope = handler_input.request_envelope
    service_client_fact = handler_input.service_client_factory
    response_builder = handler_input.response_builder
    speech_text = ""
    address = ''
    sorry_text = 'Sorry, no stop found near your address {0}. Please check the address saved in the system and try again'
    if not (req_envelope.context.system.user.permissions and req_envelope.context.system.user.permissions.consent_token):
        handler_input.response_builder.speak(NOTIFY_MISSING_PERMISSIONS).set_should_end_session(True)
        return handler_input.response_builder

    try:
        device_id = req_envelope.context.system.device.device_id
        device_addr_client = service_client_fact.get_device_address_service()
        addr = device_addr_client.get_full_address(device_id)

        if addr.address_line1 is None and addr.state_or_region is None:
            handler_input.response_builder.speak(NO_ADDRESS).set_should_end_session(True)
        else:
            address = '{0}, {1}, {2}, {3}, {4} {5}'.format(
                addr.address_line1, addr.address_line2, addr.city,
                addr.state_or_region, addr.postal_code, addr.country_code)
            # get Lat Long gecode
            param = urlencode({'address': address, 'key': GEO_LOCATION_API_KEY})
            response = requests.get('https://maps.googleapis.com/maps/api/geocode/json?', param).json()
            stop_list = list()
            if response['status'].lower() == 'ok':
                location = response['results'][0]['geometry']['location']
                print(location)
                lat_long = [location['lat'], location['lng']]
                # lat_long = [-37.824170, 145.060789]
                response = requests.get(getUrl('/v3/stops/location/{0},{1}'.format(lat_long[0], lat_long[1])))
                apl_doc = load_apl_document('apl_nearby_stops.json')
                data_source = apl_doc['datasources']
                data_source['bodyTemplate2Data']['textContent']['title']['text'] = 'Nearby Stops'
                data_source['bodyTemplate2Data']['textContent']['subtitle']['text'] = address
                if response.status_code == 200:
                    i = 0
                    for st in response.json()['stops']:
                        # take only 5 stops
                        if i < 5:
                            stop_list.append('stop name is {0}, stop distance  is {1} meters and stop mode is {2}'.format(
                                st['stop_name'],
                                int(st['stop_distance']),
                                get_mode_name(st['route_type'])
                            ))
                            data_source['bodyTemplate2Data']['textContent']['primaryText'+ str(i+1)]['text'] = str.format(
                                '{0}. Stop Name: {1}, Stop Distance: {2}, Mode: {3}',
                                i + 1,
                                st['stop_name'],
                                int(st['stop_distance']),
                                get_mode_name(st['route_type']))
                            i = i + 1

                    if len(stop_list) > 0:
                        speech_text = ' Nearby stops are {0}'.format(", ".join(stop_list))
                        speech_text = speech_text.replace('&', 'and')
                        speech_text = speech_text.replace('#', ' ')

                    else:
                        speech_text = sorry_text.format(address)
                        data_source['bodyTemplate2Data']['textContent']['primaryText1']['text'] = sorry_text.format(address)

                else:
                    speech_text = sorry_text.format(address)
                    data_source['bodyTemplate2Data']['textContent']['primaryText1']['text'] = sorry_text.format(address)



            elif response['status'] == 'INVALID_REQUEST':
                speech_text = 'Sorry, device address is not a invalid address. Please check and try again'
            else:
                speech_text = "Sorry, there is some problem in getting the required information. Please try later"
                print('error in getting response from PTV {0}'.format(response['status']))
            print(speech_text)
            if is_apl_supported(handler_input):
                handler_input.response_builder.speak(speech_text).set_should_end_session(True).add_directive(
                    RenderDocumentDirective(
                        token="NearbyStops",
                        document=apl_doc['document'],
                        datasources=data_source
                    ))
            else:
                handler_input.response_builder.speak(speech_text).set_should_end_session(True)


        return
    except ServiceException:
        handler_input.response_builder.speak(ERROR)
        return response_builder.response
    except Exception as e:
        raise e


def get_and_fill_stop_list(handler_input, route_type, current_route_id, current_route_name):
    stops_name_id_pairs = get_all_stops_of_route(route_type, current_route_id)
    # write data to dynamoDB
    stops_data = dict()
    stops_data["route_type"] = route_type
    stops_data["route_id"] = current_route_id
    stops_data["route_stops"] = stops_name_id_pairs
    # write stops of the route to fetch in paging
    client = boto3.client('dynamodb')
    response = client.update_item(
        TableName='victoria-trans-info',
        Key={'data_type': {'S': 'route_stops'}, },
        AttributeUpdates={'data_value': {'Value': {'S': json.dumps(stops_data)}}, }
    )
    handler_input.attributes_manager.session_attributes['current_route_name'] = current_route_name
    fill_stops_list(handler_input, stops_name_id_pairs, current_route_name, 0)
    return handler_input.response_builder.response

# ############################ Intent Handlers  #######################################################################


@sb.request_handler(can_handle_func=is_request_type("LaunchRequest"))
def launch_request_handler(handler_input):
    speech_text = LAUNCH_TEXT
    handler_input.attributes_manager.session_attributes['current_index'] = 0
    handler_input.attributes_manager.session_attributes['previous_intent'] = ""
    handler_input.attributes_manager.session_attributes['current_mode'] = ""
    handler_input.attributes_manager.session_attributes['current_route_name'] = ""

    # save_all_routes
    try:
        save_all_routes_dynamodb(handler_input)
    except:
        print('error while fetching all routes')
    go_home_handler(handler_input, speech_text, False)
    return handler_input.response_builder.response


@sb.request_handler(can_handle_func=is_request_type("Alexa.Presentation.APL.UserEvent"))
def alexa_user_event_request_handler(handler_input: HandlerInput):
    # Handler for Skill Launch
    arguments = handler_input.request_envelope.request.arguments
    item_selected = arguments[0]
    item_ordinal = arguments[1]
    item_title = arguments[2]
    route_type = int()
    if item_selected == 'Logo':
        go_home_handler(handler_input, "", True)
    if item_selected == 'Mode':
        handler_input.attributes_manager.session_attributes['previous_intent'] = "GetRoutesIntent"
        fill_routes(handler_input, item_title)
    if item_selected == 'Route':
        handler_input.attributes_manager.session_attributes['previous_intent'] = "GetRouteStops"

        route_type = get_route_type(str.lower(handler_input.attributes_manager.session_attributes['current_mode']))
        print('filling stops for  route_type = {0}, item_ordinal = {1} , item_title = {2}'.format(route_type, item_ordinal, item_title))
        get_and_fill_stop_list(handler_input, route_type, item_ordinal, item_title)

    if item_selected == 'Stop':

        _route_type_name = handler_input.attributes_manager.session_attributes['current_mode']
        _route_type = get_route_type(str.lower(handler_input.attributes_manager.session_attributes['current_mode']))
        get_departures_for_mode_and_stop(handler_input, _route_type,_route_type_name, item_title)

    return handler_input.response_builder.response


@sb.request_handler(can_handle_func=is_intent_name("GetModeIntent"))
def get_modes_intent_handler(handler_input):
    speech_text = ""
    query = getUrl(api_get_route_types)
    response = requests.get(query)
    route_types = list()
    if response.status_code == 200:
        for item in response.json()['route_types']:
            route_types.append(item['route_type_name'])

        speech_text = 'Available modes of transport are ' + ", ".join(route_types)
        if is_apl_supported(handler_input):
            data_source = load_apl_document("apl_mode_info.json")['datasources']
            data_source['bodyTemplate2Data']['textContent']['primaryText']['text'] = speech_text
            handler_input.response_builder.speak(speech_text).set_should_end_session(True).add_directive(
                RenderDocumentDirective(
                    token="GetModeIntent",
                    document=load_apl_document("apl_mode_info.json")['document'],
                    datasources=data_source
            ))
        else:
            handler_input.response_builder.speak(speech_text).set_should_end_session(True)
    else:
        speech_text = "Sorry! There is some problem in finding the data. Please try again"
        handler_input.response_builder.speak(speech_text).set_should_end_session(False)
    return handler_input.response_builder.response


@sb.request_handler(can_handle_func=is_intent_name("SearchNearbyStopsIntent"))
def get_nearby_stops_intent_handler(handler_input):
    get_nearby_stop(handler_input)
    return handler_input.response_builder.response


@sb.request_handler(can_handle_func=is_intent_name("GetRoutesIntent"))
def get_routes_intent_handler(handler_input):
    slots = handler_input.request_envelope.request.intent.slots
    dialog_state = handler_input.request_envelope.request.dialog_state
    intent_request = handler_input.request_envelope.request.intent
    handler_input.attributes_manager.session_attributes['previous_intent'] = "GetRoutesIntent"
    if 'mode' in slots:
        mode_value = str.lower(slots['mode'].value)
    else:
        mode_value = None

    speech_text = "Sorry! Could not find the route names for given input. Please try again"
    current_mode_id = ""

    if dialog_state.value != "COMPLETED" and mode_value is None:
        handler_input.response_builder.set_should_end_session(False)
        handler_input.response_builder.add_directive(DelegateDirective(updated_intent=intent_request))
        return handler_input.response_builder.response

    else:
        # remember current mode entered by user
        fill_routes(handler_input, mode_value)

        return handler_input.response_builder.response


@sb.request_handler(can_handle_func=is_intent_name("GetRouteStops"))
def get_routes_stops_intent_handler(handler_input):
    slots = handler_input.request_envelope.request.intent.slots
    dialogstate = handler_input.request_envelope.request.dialog_state
    intent_request = handler_input.request_envelope.request.intent
    handler_input.attributes_manager.session_attributes['previous_intent'] = "GetRouteStops"
    if 'mode' in slots:
        mode_value = str.lower(slots['mode'].value)
    else:
        mode_value = None
    if 'route' in slots:
        route_value = str.lower(slots['route'].value)
    else:
        route_value = None

    speech_text = "Sorry! Could not find the stop names for given input. Please try again"
    current_mode_id = ""

    if dialogstate.value != "COMPLETED" and (mode_value is None or route_value is None):
        handler_input.response_builder.set_should_end_session(False)
        handler_input.response_builder.add_directive(DelegateDirective(updated_intent=intent_request))
        return handler_input.response_builder.response

    else:
        # print(str.format("Getting stops for mode = {0} and for route = {1}", mode_value, route_value))
        # remember current mode entered by user
        handler_input.attributes_manager.session_attributes['current_mode'] = mode_value

        all_routes = list()
        current_route_names_list = list()
        routes_name_id_map = dict()
        current_route_name = ""
        current_route_id = ""
        route_type = int()

        if get_route_type(str.lower(mode_value)) is not None:
            route_type = get_route_type(str.lower(mode_value))
            all_routes = get_all_routes(route_type)

            for item in all_routes:
                if item['route_type'] == route_type:
                    current_route_names_list.append(item['route_name'])
                    routes_name_id_map[item['route_name']] = item['route_id']
                    if route_value.lower() == str.lower(item['route_name']):
                        current_route_name = item['route_name']
                        current_route_id = item['route_id']

            # check if exact match not found than try partial match
            if current_route_name == "":
                for item in all_routes:
                    if item['route_type'] == route_type:
                        if route_value.lower() in str.lower(item['route_name']):
                            current_route_name = item['route_name']
                            current_route_id = item['route_id']
                            break

            # if not match found
            if current_route_name != "":
                # print('finding stops for mode = {0} route = {1} route_id = {2} and route_type = {3} '.format(mode_value, current_route_name,current_route_id, route_type))
                get_and_fill_stop_list(handler_input, route_type, current_route_id, current_route_name)

        else:
            handler_input.response_builder.speak(speech_text).set_should_end_session(False)
        return handler_input.response_builder.response


@sb.request_handler(can_handle_func=is_intent_name("GetDeparturesIntent"))
def get_departure_intent_handler(handler_input):
    slots = handler_input.request_envelope.request.intent.slots
    dialog_state = handler_input.request_envelope.request.dialog_state
    intent_request = handler_input.request_envelope.request.intent
    handler_input.attributes_manager.session_attributes['previous_intent'] = "GetDeparturesIntent"

    if 'mode' in slots:
        mode_value = slots['mode'].value
    else:
        mode_value = None
    if 'stop' in slots:
        stop_value = slots['stop'].value
    else:
        stop_value = None

    if dialog_state.value != "COMPLETED" and (mode_value is None or stop_value is None):
        handler_input.response_builder.set_should_end_session(False)
        handler_input.response_builder.add_directive(DelegateDirective(updated_intent=intent_request))
        return handler_input.response_builder.response
    else:

        get_departures_for_mode_and_stop(handler_input, get_route_type(mode_value.lower()),mode_value, stop_value)
        return handler_input.response_builder.response


@sb.request_handler(can_handle_func=is_intent_name("GetStopInfoIntent"))
def find_intent_handler(handler_input):
    slots = handler_input.request_envelope.request.intent.slots
    dialog_state = handler_input.request_envelope.request.dialog_state
    intent_request = handler_input.request_envelope.request.intent
    handler_input.attributes_manager.session_attributes['previous_intent'] = "GetStopInfoIntent"
    if 'stop' in slots:
        stop_value = slots['stop'].value
    else:
        stop_value = None

    if dialog_state.value != "COMPLETED" and stop_value is None:
        handler_input.response_builder.set_should_end_session(False)
        handler_input.response_builder.add_directive(DelegateDirective(updated_intent=intent_request))
        return handler_input.response_builder.response
    else:
        get_facility_for_stop(handler_input, stop_value, 'apl_stop_info.json')
        return handler_input.response_builder.response
    return handler_input.response_builder.response


@sb.request_handler(can_handle_func=is_intent_name("AMAZON.HelpIntent"))
def help_intent_handler(handler_input):
    speech_text = "Trans Info provides Information about Routes, Stops and Next Departures for various mode of transports. Mode of transports" + \
                  " are Train, Bus, Tram, Vline and Night Bus. To know about routes for trains ask get train routes. To know about stops of a route you can ask get stops. " + \
                  "to know next five departures you can ask get departures. To search for nearby stops ask search nearby stops, to know about stops facilities please ask find stop info"

    handler_input.response_builder.speak(speech_text).ask(
        "Please ask for information about victoria transports").set_should_end_session(False)
    if is_apl_supported(handler_input):
        handler_input.response_builder.add_directive(
            RenderDocumentDirective(
                token="GetLinesIntent",
                document=load_apl_document("apl_help_info.json")['document'],
                datasources=load_apl_document("apl_help_info.json")['datasources'])
        )

    return handler_input.response_builder.response


@sb.request_handler(can_handle_func=is_intent_name("AMAZON.YesIntent"))
def yes_intent_handler(handler_input):
    _mode = handler_input.attributes_manager.session_attributes['current_mode']
    _index = handler_input.attributes_manager.session_attributes['current_index']
    _route = handler_input.attributes_manager.session_attributes['current_route_name']
    if handler_input.attributes_manager.session_attributes['previous_intent'] == "GetRoutesIntent":
        fill_routes(handler_input,_mode, _index)

    elif handler_input.attributes_manager.session_attributes['previous_intent'] == "GetRouteStops":
        route_stops = get_item_from_dynamodb('route_stops')['route_stops']
        fill_stops_list(handler_input, route_stops, _route, _index)

    return handler_input.response_builder.response


@sb.request_handler(can_handle_func=is_intent_name("GoHomeIntent"))
def yes_intent_handler(handler_input):
    speech_text = "ask trans info about routes, nearby stops and departures for Public Transport Victoria. " + \
                  "You can say get departures"
    go_home_handler(handler_input, speech_text, False)
    return handler_input.response_builder.response

@sb.request_handler(can_handle_func=lambda input: is_intent_name("AMAZON.CancelIntent")(input) or
                                                  is_intent_name("AMAZON.StopIntent")(input))
def cancel_and_stop_intent_handler(handler_input):
    speech_text = "Goodbye!"
    if is_apl_supported(handler_input):
        handler_input.response_builder.add_directive(
            RenderDocumentDirective(
                token="LaunchRequest",
                document=load_apl_document("apl_goodbye_info.json")['document'],
                datasources=load_apl_document("apl_goodbye_info.json")['datasources'])
        )
    return handler_input.response_builder.response

@sb.request_handler(can_handle_func=is_intent_name("AMAZON.NoIntent"))
def no_intent_handler(handler_input):
    speech_text = "OK!"
    handler_input.response_builder.speak(speech_text).set_should_end_session(True)
    if is_apl_supported(handler_input):
        handler_input.response_builder.add_directive(
            RenderDocumentDirective(
                token="NoIntent",
                document=load_apl_document("apl_help_info.json")['document'],
                datasources=load_apl_document("apl_help_info.json")['datasources'])
        )
    return handler_input.response_builder.response


@sb.request_handler(can_handle_func=is_request_type("SessionEndedRequest"))
def session_ended_request_handler(handler_input):
    # any cleanup logic goes here

    return handler_input.response_builder.response


@sb.exception_handler(can_handle_func=lambda i, e: True)
def all_exception_handler(handler_input, exception):
    # Log the exception in CloudWatch Logs
    print(exception)
    speech = "Sorry, I didn't get it. Can you please say it again!!"
    handler_input.response_builder.speak(speech).ask(speech)
    return handler_input.response_builder.response


handler = sb.lambda_handler()
