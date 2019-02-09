from ask_sdk_core.skill_builder import SkillBuilder
import json
import copy
sb = SkillBuilder()
from ask_sdk_core.utils import is_request_type
from ask_sdk_model import Response
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_model.interfaces.alexa.presentation.apl import UserEvent
from ask_sdk_model.dialog.delegate_directive import DelegateDirective
from ask_sdk_model.interfaces.alexa.presentation.apl import RenderDocumentDirective
import requests
import  os
from ask_sdk_core.utils import is_intent_name

from hashlib import sha1
import hmac

import requests
from  urllib.parse import urlencode
BASE_URL = 'http://timetableapi.ptv.vic.gov.au'
# route_types (array of integer) is required
api_get_routes = '/v3/routes?'
# route id (integer) is required
api_get_route_info = '/v3/routes/%5B0%5D?'
# No parmaeter
api_get_route_types = '/v3/route_types'
#GET /v3/stops/route/{route_id}/route_type/{route_type}
api_get_stops_on_route = '/v3/stops/route/{0}/route_type/{1}'

# /v3/stops/route/{route_id}/route_type/{route_type}
api_get_route_stops = '/v3/stops/route/{0}/route_type/{1}'

ptv_api_key = os.environ['PTV_API_KEY']
ptv_dev_id = os.environ['PTV_DEV_ID']

number_map = {'1':'first', '2': 'second','3':'third', '4':'fourth', '5':'and fifth'}
mode_image_dict = {'train':'https://s3.amazonaws.com/aws-apl-contest/transInfo/logo/train_hi_res_512.png',
                   'bus':'https://s3.amazonaws.com/aws-apl-contest/transInfo/logo/bus_hi_res_512.png',
                   'tram':'https://s3.amazonaws.com/aws-apl-contest/transInfo/logo/tramhi_res_512.png',
                   'vline':'https://s3.amazonaws.com/aws-apl-contest/transInfo/logo/vline.png',
                   'night bus':'https://s3.amazonaws.com/aws-apl-contest/transInfo/logo/nightbus_hi_res_512.png'}

def getUrl(request):
    request = request + ('&' if ('?' in request) else '?')
    raw = request + 'devid={0}'.format(ptv_dev_id)
    bkey = bytearray(ptv_api_key, 'utf-8')
    hashed = hmac.new(bkey, raw.encode('utf-8'), sha1)
    signature = hashed.hexdigest()
    return BASE_URL + raw + '&signature={1}'.format(ptv_dev_id, signature)

def is_apl_supported(handler_input):

    if  handler_input.request_envelope.context.system.device.supported_interfaces.alexa_presentation_apl is None:
        return False
    else:
        return True


def load_apl_document(file_path):
    # type: (str) -> Dict[str, Any]
    """Load the apl json document at the path into a dict object."""
    with open(file_path) as f:
        return json.load(f)

def get_all_routes():
    try:
        response = requests.get(getUrl('/v3/routes'))
        return response.json()['routes']
    except:
        print('Source: get_all_routes, error while getting all routes:')

def get_all_sotps_of_route(route_type, route_id):

    api_query = '/v3/stops/route/{0}/route_type/{1}'.format(route_id, route_type)
    print('quesry for get_all_sotps_of_route = {0}'.format(api_query))
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
        print('stop name list {0}'.format(st_list))
        for st in st_list:
            if str.lower(stop_name) == str.lower(st):
                return [st, stop_name_ids[st]]
        # try partial first match
        for st in st_list:
            if stop_name.lower() in st.lower():
                return [st, stop_name_ids[st]]
    return None

# def get_departures_for_stop(stop_id:int, route_type:int, route_id:int):
#     if route_id is None:
#         # dont care about route
#         api = '/v3/departures/route_type/{0}/stop/{1}'.format(route_type, stop_id)
#     else:
#         # find  route specific departures
#         api = '/v3/departures/route_type/{0}/stop/{1}/route/{2}'.format(route_type, stop_id,route_id)
#     print('finding departures for URL = '.format(api))
#     response = requests.get(getUrl(api))
#
#     if response.status_code == 200:
#         return response.json()['departures']
#     else:
#         print('Source  = get_direction_for_stop,  Error code = {0}'.format(response.status_code))
#         return None

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
def get_departures_for_mode_and_stop(handler_input, route_type, search_term, apl_template):
    param_query = '/v3/search/{0}?route_types={1}&include_addresses=false&include_outlets=false&match_route_by_suburb=false&match_stop_by_gtfs_stop_id=false'.format(search_term,route_type)
    res = requests.get(getUrl(param_query)).json()
    apl_doc = load_apl_document(apl_template)['document']
    apl_data = load_apl_document(apl_template)['datasources']

    i=0
    dep_list = list()
    if res.get('stops') is not None:
        stop_id  = res['stops'][0]['stop_id']
        stop_name =  res['stops'][0]['stop_name']
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
                break
        if len(dep_list)>0:
            if mode_image_dict.get(route_type.lower()) is not None:
                apl_data['bodyTemplate2Data']['image']  = mode_image_dict.get(route_type.lower())
            apl_data['bodyTemplate2Data']['textContent']['title']['text'] = stop_name
            apl_data['bodyTemplate2Data']['textContent']['subtitle']['text'] = 'Mode: {0}'.format(route_type)
            apl_data['bodyTemplate2Data']['textContent']['primaryText']['text'] = 'Mode: {0}'.format(route_type)
            speech_text = 'At stop {0}, next {1} departures are  '.format(stop_name, len(dep_list))
            speech = list()
            display_text = list()
            for i in range(len(dep_list)):
                time = dep_list[i]['scheduled_departure_utc'].split('T')[1].replace('Z', '') + ' UTC'
                rt = dep_list[i]['route_name']
                dr = dep_list[i]['direction']
                pt = dep_list[i]['platform_number']
                speech.append('At {0} for route {1} in direction {2} at platform number {3} '.format(time, rt,dr ,pt))
                display_text.append('Time: {0} \n Route: {1}  Direction:  {2}\nPlatform: {3}'.format(time,rt,dr, pt ))

            speech_text = speech_text + ", ".join(speech)
            apl_data['bodyTemplate2Data']['textContent']['primaryText']['text'] = "\n\n".join(display_text)
            if is_apl_supported(handler_input):
                handler_input.response_builder.speak(speech_text).set_should_end_session(
                    True).add_directive(
                    RenderDocumentDirective(
                        token="GetDepartures",
                        document=apl_doc,
                        datasources=apl_data
                    )
                )
            else:
                handler_input.response_builder.speak(speech_text).set_should_end_session(True)

    else:
        speech_text = "Sorry I could not find the information for {0}. Please try again".format(search_term)
        handler_input.response_builder.speak(speech_text).set_should_end_session(True)

    return handler_input

def fill_routes(handler_input, mode_value):
    handler_input.attributes_manager.session_attributes['current_mode'] = mode_value
    if 'mode_name_type_map' in handler_input.attributes_manager.session_attributes:
        mode_name_type_map = handler_input.attributes_manager.session_attributes['mode_name_type_map']
    else:
        mode_name_type_map = get_route_types()[1]

    handler_input.attributes_manager.session_attributes['mode_name_type_map'] = mode_name_type_map
    all_routes = list()
    current_route_names_list = list()
    routes_name_id_map = dict()
    if mode_name_type_map.get(str.lower(mode_value)) is not None:
        all_routes = get_all_routes()
        route_type = mode_name_type_map.get(str.lower(mode_value))
        list_doc = load_apl_document('apl_route_list.json')
        data_source = list_doc['datasources']
        data_source['listTemplate1Metadata']['title'] = "Route List for {0}".format(mode_value)
        route_list = list()
        for item in all_routes:

            if item['route_type'] == route_type:
                current_route_names_list.append(item['route_name'])
                routes_name_id_map[item['route_name']] = item['route_id']
        # remember current routes id name map for the session
        # handler_input.attributes_manager.session_attributes['routes_name_id_map'] = routes_name_id_map

        i = 0
        speech_text_temp = ""
        for item in current_route_names_list:
            if i < 20:
                route_list_item = copy.deepcopy(load_apl_document('apl_route_list_item_template.json'))
                route_list_item['ordinalNumber'] = i + 1
                route_list_item['textContent']['primaryText']['text'] = item
                route_list_item['textContent']['ecoSpotText']['text'] = item[:30] + "..." if len(item)>33 else item
                route_list_item['listItemIdentifier'] = item
                route_list_item['token'] = mode_value
                route_list.append(route_list_item)
                if i == 0:
                    speech_text_temp = item.replace("&", "and")
                else:
                    speech_text_temp = speech_text_temp + ",  " + item.replace("&", "and")
                i = i + 1

        data_source['listTemplate1ListData']['listPage']['listItems'] = route_list

        speech_text = 'Total {0} routes available for {1} and some of these are {2} '.format(
            len(current_route_names_list), mode_value, speech_text_temp)
        if is_apl_supported(handler_input):
            handler_input.response_builder.speak(speech_text).ask(speech_text).set_should_end_session(True).add_directive(
                RenderDocumentDirective(
                    token="FIndRoutes",
                    document=list_doc['document'],
                    datasources=data_source))
        else:
            handler_input.response_builder.speak(speech_text).ask(speech_text).set_should_end_session(True)


    return

"""
get facilities for a station based on the search query. first search for stop in Train and then search stop in
VLine
"""
def get_facility_for_stop(handler_input, search_term, apl_template):
    search_term = search_term.replace(' ', '%20')
    param_query = '/v3/search/{0}?route_types=0&route_types=3&include_addresses=false&include_outlets=false&match_route_by_suburb=false&match_stop_by_gtfs_stop_id=false'.format(search_term)
    res = requests.get(getUrl(param_query)).json()
    speech_text = ""
    apl_doc = load_apl_document(apl_template)['document']
    apl_data = load_apl_document(apl_template)['datasources']
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


def fill_stops_list(handler_input, stop_name_dict, route_name):
    stops_names = list()
    stop_list = list()
    speech_text = "Sorry could not find the stop names for given input. Please try again"
    apl_doc = load_apl_document("apl_stop_list.json")['document']
    data_source = load_apl_document("apl_stop_list.json")['datasources']
    if stop_name_dict is not None:
        st_list = list(stop_name_dict.keys())
        data_source['listTemplate1Metadata']['title'] = "Stop List for Route: {0}".format(route_name)
        for i in range(len(st_list)):
            stops_names.append(st_list[i])
            stop_list_item = copy.deepcopy(load_apl_document('apl_stop_list_item_template.json'))
            stop_list_item['ordinalNumber'] = i + 1
            stop_list_item['textContent']['primaryText']['text'] = st_list[i]
            stop_list_item['textContent']['ecoSpotText']['text'] = st_list[i][:30] + "..." if len(st_list[i]) > 33 else st_list[i]
            stop_list_item['listItemIdentifier'] = st_list[i]
            stop_list_item['token'] = route_name
            stop_list.append(stop_list_item)

        data_source['listTemplate1ListData']['listPage']['listItems'] = stop_list
        speech_text = str.format('Total {0} stops for route ' + route_name + ' and these are {1}',
                                 str(len(stops_names)), ", ".join(stops_names))
    if is_apl_supported(handler_input):
        handler_input.response_builder.speak(speech_text).ask(speech_text).set_should_end_session(True).add_directive(
            RenderDocumentDirective(
                token="FIndStops",
                document=apl_doc,
                datasources=data_source)
        )
    else:
        handler_input.response_builder.speak(speech_text).ask(speech_text).set_should_end_session(True)
    return



def go_home_handler(handler_input,speech_text,end_session:bool):
    handler_input.response_builder.speak(speech_text).set_should_end_session(end_session)
    if is_apl_supported(handler_input):
        handler_input.response_builder.add_directive(
            RenderDocumentDirective(
            token="LaunchRequest",
            document=load_apl_document("apl_launch_trans_info.json")['document'],
            datasources=load_apl_document("apl_launch_trans_info.json")['datasources'])
        )

@sb.request_handler(can_handle_func=is_request_type("Alexa.Presentation.APL.UserEvent"))
def alexa_user_event_request_handler(handler_input: HandlerInput):
    # Handler for Skill Launch
    print('object_type = {0}'.format(handler_input.request_envelope.request.object_type))
    arguments = handler_input.request_envelope.request.arguments
    print('arguments = {0}'.format(arguments))
    item_selected = arguments[0]
    item_ordinal =  arguments[1]
    item_title = arguments[2]
    if item_selected == 'Logo':
        go_home_handler(handler_input, "", True)

    return handler_input.response_builder.response

@sb.request_handler(can_handle_func=is_request_type("LaunchRequest"))
def launch_request_handler(handler_input):
    speech_text = "Welcome, ask Trans Info about routes, stops and departures for Public Transport Victoria. You can say get departures"
    #get_all_routes( handler_input.attributes_manager.session_attributes)
    go_home_handler(handler_input, speech_text, False)
    return handler_input.response_builder.response

@sb.request_handler(can_handle_func=is_intent_name("GetModeIntent"))
def get_modes_request_handler(handler_input):
    speech_text = ""
    query = getUrl(api_get_route_types)
    response = requests.get(query)
    route_types = list()
    if  response.status_code == 200:
        for item in response.json()['route_types']:
            route_types.append(item['route_type_name'])

        speech_text = 'Available modes of transport are ' + ", ".join(route_types)
        if is_apl_supported(handler_input):
            handler_input.response_builder.speak(speech_text).set_should_end_session(True).add_directive(
                RenderDocumentDirective(
                    token="GetModeIntent",
                    document=load_apl_document("apl_launch_template.json")['document'],
                    datasources=load_apl_document("apl_launch_template.json")['datasources'])
            )
        else:
            handler_input.response_builder.speak(speech_text).set_should_end_session(True)
    else:
        speech_text = "Sorry there is problem in finding the data. Please try again"
        handler_input.response_builder.speak(speech_text).set_should_end_session(False)
    return handler_input.response_builder.response

@sb.request_handler(can_handle_func=is_intent_name("GetLinesIntent"))
def get_line_request_handler(handler_input):
    speech_text = ""

    line_names = get_line_names()
    if line_names is not None:
        speech_text = 'line names are ' + ", ".join(line_names[0])
        handler_input.attributes_manager.session_attributes['routes_name_id_map'] = line_names[1]
        if is_apl_supported(handler_input):
            handler_input.response_builder.speak(speech_text).set_should_end_session(True).add_directive(
                RenderDocumentDirective(
                    token="GetLinesIntent",
                    document=load_apl_document("apl_launch_trans_info.json")['document'],
                    datasources=load_apl_document("apl_launch_trans_info.json")['datasources'])
            )
        else:
            handler_input.response_builder.speak(speech_text).set_should_end_session(True)


    else:
        speech_text = "Sorry there is problem in finding line names. Please try again"
        handler_input.response_builder.speak(speech_text).set_should_end_session(
             False)
    return handler_input.response_builder.response

# @sb.request_handler(can_handle_func=is_intent_name("GetLineStopsIntent"))
# def get_lines_stops_intent_handler(handler_input):
#
#     slots = handler_input.request_envelope.request.intent.slots
#     dialogstate = handler_input.request_envelope.request.dialog_state
#     intent_request = handler_input.request_envelope.request.intent
#     print('slot line = ' + slots['line'].value)
#     print(handler_input)
#     if handler_input.attributes_manager.session_attributes is None:
#         print('attributes_manager is null')
#         handler_input.attributes_manager.session_attributes = {}
#     else:
#         print('attributes_manager', handler_input.attributes_manager.session_attributes)
#     if 'line' in slots:
#         print('slot line = ' + slots['line'].value)
#         line_value = slots['line'].value
#     else:
#         line_value = None
#
#     speech_text = ""
#     route_id = ""
#
#     if dialogstate.value != "COMPLETED" or line_value is None:
#         handler_input.response_builder.set_should_end_session(False)
#         handler_input.response_builder.add_directive(DelegateDirective(updated_intent=intent_request))
#         return handler_input.response_builder.response
#
#     else:
#         print(str.format("Getting Stops for line = {0}", line_value ))
#         if 'routes_name_id_map' in handler_input.attributes_manager.session_attributes:
#             routes_name_id_map = handler_input.attributes_manager.session_attributes['routes_name_id_map']
#         else:
#             print('session attributes were empty')
#             stops_names = list()
#             routes_name_id_map = get_line_names()[1]
#             print(routes_name_id_map)
#             handler_input.attributes_manager.session_attributes['routes_name_id_map'] = routes_name_id_map
#
#             if routes_name_id_map.get(line_value) is not None:
#                 route_id  = routes_name_id_map.get(line_value)
#                 api_query = '/v3/stops/route/{0}/route_type/0'.format(route_id)
#                 response = requests.get(getUrl(api_query))
#
#                 if  response.status_code == 200:
#                     stops_list = response.json()['stops']
#                     print(stops_list)
#                     handler_input.attributes_manager.session_attributes['stops_list'] = response.json()['stops']
#
#                     for i in range(len(stops_list)):
#                         stops_names.append(stops_list[i]['stop_name'])
#
#                     speech_text = 'stops for line ' + line_value + ' are ' + ", ".join(stops_names)
#
#                 else:
#                     speech_text = " Sorry could not find the stop names for given input. Please try again"
#             else:
#                 handler_input.response_builder.add_directive(DelegateDirective(updated_intent=intent_request))
#
#         handler_input.response_builder.speak(speech_text).ask(speech_text).set_card(
#             SimpleCard("Hello World", speech_text)).add_directive(
#                 RenderDocumentDirective(
#                     token="pagerToken",
#                     document=load_apl_document("apl_launch_trans_info.json")['document'],
#                     datasources=load_apl_document("apl_launch_trans_info.json")['datasources']
#                 )
#         )
#         return handler_input.response_builder.response

@sb.request_handler(can_handle_func=is_intent_name("GetRoutesIntent"))
def get_routes_intent_handler(handler_input):

    slots = handler_input.request_envelope.request.intent.slots
    dialogstate = handler_input.request_envelope.request.dialog_state
    intent_request = handler_input.request_envelope.request.intent


    if 'mode' in slots:
        print('mode = ' + slots['mode'].value)
        mode_value = str.lower(slots['mode'].value)
    else:
        mode_value = None

    speech_text = "Sorry could not find the route names for given input. Please try again"
    current_mode_id = ""

    if dialogstate.value != "COMPLETED" and mode_value is None:
        handler_input.response_builder.set_should_end_session(False)
        handler_input.response_builder.add_directive(DelegateDirective(updated_intent=intent_request))
        return handler_input.response_builder.response

    else:
        print(str.format("Getting routes for mode = {0}", mode_value ))
        # remember current mode entered by user
        fill_routes(handler_input, mode_value)

        return handler_input.response_builder.response

@sb.request_handler(can_handle_func=is_intent_name("GetRouteStops"))
def get_routes_stops_intent_handler(handler_input):

    slots = handler_input.request_envelope.request.intent.slots
    dialogstate = handler_input.request_envelope.request.dialog_state
    intent_request = handler_input.request_envelope.request.intent

    if 'mode' in slots:
        print('mode = ' + slots['mode'].value)
        mode_value = str.lower(slots['mode'].value)
    else:
        mode_value = None

    if 'route' in slots:
        print('route = ' + slots['route'].value)
        route_value = str.lower(slots['route'].value)
    else:
        route_value = None

    speech_text = "Sorry could not find the stop names for given input. Please try again"
    current_mode_id = ""

    if dialogstate.value != "COMPLETED" and ( mode_value is None or route_value is None):
        handler_input.response_builder.set_should_end_session(False)
        handler_input.response_builder.add_directive(DelegateDirective(updated_intent=intent_request))
        return handler_input.response_builder.response

    else:
        print(str.format("Getting stops for mode = {0} and for route = {1}", mode_value, route_value ))
        # remember current mode entered by user
        handler_input.attributes_manager.session_attributes['current_mode'] = mode_value
        if 'mode_name_type_map' in handler_input.attributes_manager.session_attributes:
            mode_name_type_map = handler_input.attributes_manager.session_attributes['mode_name_type_map']
        else:
            mode_name_type_map = get_route_types()[1]
            handler_input.attributes_manager.session_attributes['mode_name_type_map'] = mode_name_type_map

        all_routes = list()
        current_route_names_list = list()
        routes_name_id_map = dict()
        current_route_name = ""
        current_route_id = ""
        route_type = int()

        if mode_name_type_map.get(str.lower(mode_value)) is not None:
            all_routes = get_all_routes()
            route_type = mode_name_type_map.get(str.lower(mode_value))
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
                print('finding stops for mode = {0} route = {1} route_id = {2} and route_type = {3} '.format(mode_value, current_route_name,current_route_id, route_type))
                stops_name_id_pairs = get_all_sotps_of_route(route_type, current_route_id)
                fill_stops_list(handler_input, stops_name_id_pairs, current_route_name)
                return handler_input.response_builder.response

        handler_input.response_builder.speak(speech_text).ask(speech_text)
        return handler_input.response_builder.response

@sb.request_handler(can_handle_func=is_intent_name("GetDeparturesIntent"))
def get_depature_intent_handler(handler_input):
    slots = handler_input.request_envelope.request.intent.slots
    dialogstate = handler_input.request_envelope.request.dialog_state
    intent_request = handler_input.request_envelope.request.intent

    if 'mode' in slots:
        print('mode = {0}'.format(slots['mode'].value))
        mode_value = slots['mode'].value
    else:
        mode_value = None

    if 'stop' in slots:
        print('stop = {0}'.format(slots['stop'].value))
        stop_value = slots['stop'].value
    else:
        stop_value = None

    if dialogstate.value != "COMPLETED" and (mode_value is None or stop_value is None):
        handler_input.response_builder.set_should_end_session(False)
        handler_input.response_builder.add_directive(DelegateDirective(updated_intent=intent_request))
        return handler_input.response_builder.response
    else:
        get_departures_for_mode_and_stop(handler_input, mode_value, stop_value, 'apl_trans_info_departures.json')
        return handler_input.response_builder.response


@sb.request_handler(can_handle_func=is_intent_name("FindFacilitiesIntent"))
def find_intent_handler(handler_input):
    slots = handler_input.request_envelope.request.intent.slots
    dialogstate = handler_input.request_envelope.request.dialog_state
    intent_request = handler_input.request_envelope.request.intent
    if 'stop' in slots:
        stop_value = slots['stop'].value
    else:
        stop_value = None

    if dialogstate.value != "COMPLETED" and stop_value is None:
        handler_input.response_builder.set_should_end_session(False)
        handler_input.response_builder.add_directive(DelegateDirective(updated_intent=intent_request))
        return handler_input.response_builder.response
    else:
        get_facility_for_stop(handler_input, stop_value, 'apl_stop_info.json')
        return handler_input.response_builder.response

@sb.request_handler(can_handle_func=is_intent_name("AMAZON.HelpIntent"))
def help_intent_handler(handler_input):
    speech_text = "Trans Info provides Information about Routes, Stops and Next Departures for various mode of transports. Mode of transports" +\
                  " are Train, Bus, Tram, Vline and Night Bus. To know about routes for trains ask get train routes. To know about stops of a route you can ask get stops. " +\
                  "to know next five departures you can ask get departures. To know about stops facilities please ask fins stop info"

    handler_input.response_builder.speak(speech_text).ask("Please ask for information about victoria transports").set_should_end_session(False)
    if is_apl_supported(handler_input):
        handler_input.response_builder.add_directive(
            RenderDocumentDirective(
                token="GetLinesIntent",
                document=load_apl_document("apl_help_info.json")['document'],
                datasources=load_apl_document("apl_help_info.json")['datasources'])
        )

    return handler_input.response_builder.response

@sb.request_handler(can_handle_func=is_intent_name("GetModesIntent"))
def get_modes_intent_handler(handler_input):
    speech_text = ""

    routes_types = get_route_types()
    if routes_types is not None:
        speech_text = 'transport modes are ' + ", ".join(routes_types[0])
        handler_input.attributes_manager.session_attributes['mode_name_type_map'] = routes_types[1]
    else:
        # if dynamic content is not available
        speech_text = "transport modes are train, tram, bus, vline and night bus"

    if is_apl_supported(handler_input):
        handler_input.response_builder.speak(speech_text).set_should_end_session(True).add_directive(
            RenderDocumentDirective(
                token="GetModesIntent",
                document=load_apl_document("apl_launch_template.json")['document'],
                datasources=load_apl_document("apl_launch_template.json")['datasources'])
            )
    else:
        handler_input.response_builder.speak(speech_text).set_should_end_session(True)

    return handler_input.response_builder.response

@sb.request_handler(can_handle_func=lambda input :is_intent_name("AMAZON.CancelIntent")(input) or
        is_intent_name("AMAZON.StopIntent")(input))
def cancel_and_stop_intent_handler(handler_input):
    speech_text = "Goodbye!"
    go_home_handler(handler_input, speech_text, True)
    return handler_input.response_builder.response

@sb.request_handler(can_handle_func=is_request_type("SessionEndedRequest"))
def session_ended_request_handler(handler_input):
    #any cleanup logic goes here

    return handler_input.response_builder.response

@sb.exception_handler(can_handle_func=lambda i, e: True)
def all_exception_handler(handler_input, exception):
    # Log the exception in CloudWatch Logs
    print(exception)

    speech = "Sorry, I didn't get it. Can you please say it again!!"
    handler_input.response_builder.speak(speech).ask(speech)
    return handler_input.response_builder.response

handler = sb.lambda_handler()