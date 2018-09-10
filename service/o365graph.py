from flask import Flask, request, Response
import os
import requests
import logging
import json
import dotdictify
import urllib
from time import sleep
import ast



app = Flask(__name__)
logger = None
format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logger = logging.getLogger('o365graph-service')

# Log to stdout
stdout_handler = logging.StreamHandler()
stdout_handler.setFormatter(logging.Formatter(format_string))
logger.addHandler(stdout_handler)
logger.setLevel(logging.DEBUG)

##getting token from oauth2
def get_token():
    logger.info("Creating header")
    headers= {}
    payload = {
        "client_id":os.environ.get('client_id'),
        "client_secret":os.environ.get('client_secret'),
        "grant_type": os.environ.get('grant_type'),
        "resource": os.environ.get('resource')
    }
    resp = requests.post(url=os.environ.get('token_url'), data=payload, headers=headers).json()
    token = dotdictify.dotdictify(resp).access_token
    logger.info("Received access token from " + os.environ.get('token_url'))
    return token
#decode bytes in response
def decode_resp(obj):
    if isinstance(obj, (bytes, bytearray)):
        return obj.decode('ASCII')

# def get_membership(obj, access_token, path):
#     user ={}
#     url = os.environ.get('base_url') + path
#     headers = {'Authorization': 'Bearer ' + access_token, 'Accept': 'application/json'}
#     for k, v in obj.items():
#         if k is not "id" and v is not None:
#             user[k] = v
#         if k == "id":
#             try:
#                 url += v + "memberOf"
#                 resp = requests.get(url, headers=headers)
#             except Exception:
#
#     else:
#         pass
#     return user
#if groups, get this for the techMikael_schema
def get_schema(obj, access_token, path):
    schema_res = {}
    url = os.environ.get('base_url') + path
    headers = {'Authorization': 'Bearer '+ access_token, 'Accept': 'application/json'}
    for k, v in obj.items():
        if k is not "id" and v is not None:
            schema_res[k] = v

        if k == "id":
            url += v + "?$select=id,displayName,techmikael_GenericSchema"
            resp =requests.get(url, headers=headers)
            schema_res = json.loads(decode_resp(resp.content))


    else:
        pass
    return schema_res

class DataAccess:
#all lists that needs to be updated
    def __get_all_lists(self, path):
        logger.info("Fetching data from url: %s", path)
        url=os.environ.get("base_url") + path
        req = requests.get(url, headers=headers)

        if req.status_code != 200:
            logger.error("Unexpected response status code: %d with response text %s" % (req.status_code, req.text))
            raise AssertionError("Unexpected response status code: %d with response text %s" % (req.status_code, req.text))
        clean = json.loads(req.text)
        for entity in clean:
            yield entity
#main get function, will probably run most via path:path
    def __get_all_paged_entities(self, path):
        logger.info("Fetching data from paged url: %s", path)
        #url = os.environ.get("base_url") + path + os.environ.get("limit")
        url = "https://graph.microsoft.com/v1.0/groups?$select=id,deletedDateTime,classification,createdDateTime,creationOptions,description,displayName,groupTypes,mail,mailEnabled,mailNickname,onPremisesLastSyncDateTime,onPremisesSecurityIdentifier,onPremisesSyncEnabled,preferredDataLocation,proxyAddresses,renewedDateTime,resourceBehaviorOptions,resourceProvisioningOptions,securityEnabled,visibility,onPremisesProvisioningErrors,techmikael_GenericSchema&$expand=members"
        access_token = get_token()
        next_page = url
        page_counter = 1
        while next_page is not None:
            if os.environ.get('sleep') is not None:
                logger.info("sleeping for %s milliseconds", os.environ.get('sleep') )
                sleep(float(os.environ.get('sleep')))

            logger.info("Fetching data from url: %s", next_page)
            req = requests.get(next_page, headers={"Authorization": "Bearer " + access_token})
            if req.status_code != 200:
                logger.error("Unexpected response status code: %d with response text %s" % (req.status_code, req.text))
                raise AssertionError ("Unexpected response status code: %d with response text %s"%(req.status_code, req.text))
            dict = dotdictify.dotdictify(json.loads(req.text))
            logger.info(dict)
            for entity in dict.get(os.environ.get("entities_path")):
                if path == os.environ.get(('group_url')):
                    yield get_schema(entity, access_token, path)
                # if path == os.environ.get(('user_url')):
                #     yield get_membership(entity, access_token, path)
                else:
                    yield(entity)

            if dict.get(os.environ.get('next_page')) is not None:
                page_counter+=1
                next_page = dict.get(os.environ.get('next_page'))
            else:
                next_page = None
        logger.info('Returning entities from %i pages', page_counter)

    def get_paged_entities(self,path):
        print("getting all paged")
        return self.__get_all_paged_entities(path)

    def get_users(self, path):
        print('getting all users')
        return self.__get_all_users(path)

data_access_layer = DataAccess()


def stream_json(clean):
    first = True
    yield '['
    for i, row in enumerate(clean):
        if not first:
            yield ','
        else:
            first = False
        yield json.dumps(row)
    yield ']'

@app.route("/<path:path>", methods=["GET", "POST"])
def get(path):
    if request.method == "POST":
        path = request.get_json()
    entities = data_access_layer.get_paged_entities(path)
    return Response(
        stream_json(entities),
        mimetype='application/json'
    )

@app.route("/user", methods=["GET", "POST"])
def get_user():
    if request.method == "POST":
        path = request.get_json()
        for k, v in path.items():
            if k == "id":
                path = v
                logger.info(path)
            else:
                break
        entities = data_access_layer.get_paged_entities(path)
        return Response(
            stream_json(entities),
            mimetype='application/json'
        )
    else:
        path = os.environ.get("user_url")
        entities = data_access_layer.get_paged_entities(path)
        return Response(
            stream_json(entities),
            mimetype='application/json'
        )

@app.route("/group", methods=["GET"])
def get_cv():
    path = os.environ.get('group_url')
    entities = data_access_layer.get_paged_entities(path)
    return Response(
        stream_json(entities),
        mimetype='application/json'
    )


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', threaded=True, port=os.environ.get('port',5000))
