import json
import boto3
from botocore.exceptions import ClientError
from decimal import Decimal

# Initialize the DynamoDB client
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
dynamodb_table = dynamodb.Table('employee_info')

status_check_path = '/status'
employee_path     = '/employee'
employees_path    = '/employees'

def handler(event, context):
    print('Request event:', event)

    # 1) Handle CORS preflight
    if event.get('httpMethod') == 'OPTIONS':
        return build_cors_preflight_response()

    try:
        method = event.get('httpMethod')
        path   = event.get('path')

        if method == 'GET' and path == status_check_path:
            return build_response(200, 'Service is operational')

        if method == 'GET' and path == employee_path:
            eid = event['queryStringParameters']['employeeid']
            return get_employee(eid)

        if method == 'GET' and path == employees_path:
            return get_employees()

        if method == 'POST' and path == employee_path:
            body = json.loads(event['body'])
            return save_employee(body)

        if method == 'PATCH' and path == employee_path:
            body = json.loads(event['body'])
            return modify_employee(
                body['employeeId'],
                body['updateKey'],
                body['updateValue']
            )

        if method == 'DELETE' and path == employee_path:
            body = json.loads(event['body'])
            return delete_employee(body['employeeId'])

        # Not found
        return build_response(404, {'error': 'Not Found'})

    except Exception as e:
        print('Error:', e)
        return build_response(500, {'error': str(e)})

def get_employee(employee_id):
    try:
        resp = dynamodb_table.get_item(Key={'employeeid': employee_id})
        return build_response(200, resp.get('Item'))
    except ClientError as e:
        return build_response(400, {'error': e.response['Error']['Message']})

def get_employees():
    try:
        items = scan_dynamo_records({'TableName': dynamodb_table.name}, [])
        return build_response(200, items)
    except ClientError as e:
        return build_response(400, {'error': e.response['Error']['Message']})

def scan_dynamo_records(params, accumulator):
    resp = dynamodb_table.scan(**params)
    accumulator.extend(resp.get('Items', []))
    if 'LastEvaluatedKey' in resp:
        params['ExclusiveStartKey'] = resp['LastEvaluatedKey']
        return scan_dynamo_records(params, accumulator)
    return {'employees': accumulator}

def save_employee(item):
    try:
        dynamodb_table.put_item(Item=item)
        return build_response(200, {
            'Operation': 'SAVE',
            'Message': 'SUCCESS',
            'Item': item
        })
    except ClientError as e:
        return build_response(400, {'error': e.response['Error']['Message']})

def modify_employee(employee_id, update_key, update_value):
    try:
        resp = dynamodb_table.update_item(
            Key={'employeeid': employee_id},
            UpdateExpression='SET #field = :val',
            ExpressionAttributeNames={ '#field': update_key },
            ExpressionAttributeValues={ ':val': update_value },
            ReturnValues='UPDATED_NEW'
        )
        return build_response(200, {
            'Operation': 'UPDATE',
            'Message': 'SUCCESS',
            'UpdatedAttributes': resp.get('Attributes')
        })
    except ClientError as e:
        return build_response(400, {'error': e.response['Error']['Message']})

def delete_employee(employee_id):
    try:
        resp = dynamodb_table.delete_item(
            Key={'employeeid': employee_id},
            ReturnValues='ALL_OLD'
        )
        return build_response(200, {
            'Operation': 'DELETE',
            'Message': 'SUCCESS',
            'Item': resp.get('Attributes')
        })
    except ClientError as e:
        return build_response(400, {'error': e.response['Error']['Message']})

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super().default(obj)

def build_response(status_code, body_obj):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type':                'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods':'GET,POST,PATCH,DELETE,OPTIONS',
            'Access-Control-Allow-Headers':'Content-Type'
        },
        'body': json.dumps(body_obj, cls=DecimalEncoder)
    }

def build_cors_preflight_response():
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type':                'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods':'GET,POST,PATCH,DELETE,OPTIONS',
            'Access-Control-Allow-Headers':'Content-Type'
        },
        'body': ''
    }
