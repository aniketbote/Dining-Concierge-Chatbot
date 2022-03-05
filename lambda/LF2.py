import json
import boto3
import random
import requests
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError


def lambda_handler(event, context):
    # TODO implement
    client = boto3.client('sqs')
    QueueUrl = 'https://sqs.us-east-1.amazonaws.com/227712325985/Q1'
    response = client.receive_message(
        QueueUrl=QueueUrl,
        MaxNumberOfMessages=1,
        MessageAttributeNames=[
            'All'
        ],
        VisibilityTimeout=0,
        WaitTimeSeconds=0
        )
    print(response)
    
    #key used for identifying responses
    keys = list(response.keys())
    if 'Messages' not in keys:
        return {
            'statusCode': 200,
            'body': json.dumps('No messages')
        }
        
    data = json.loads(response['Messages'][0]['Body'])
    receipt_handle = response['Messages'][0]['ReceiptHandle']
    
    # Get list from elastic search
    host = 'https://search-dcc-7e5nm62qe5zyy3sqeu5tmwtp4q.us-east-1.es.amazonaws.com'
    url = host + '/_search?q=cuisine:{}&size=1000'.format(data['cuisine'])
    r = requests.get(url, auth=("test", "Test@1234")) 
    restaurant_data = json.loads(r.text)
    
    # Some default restaurents to sample from in case the fetch fails. Highly unlikely
    random_list = ['8dUaybEPHsZMgr1iKgqgMQ',
                 'msT3LrLB4fhN04HYHuFsew',
                 '4KfQnlcSu4bbTqnvGdGptw',
                 'W97siDhQbWIVa0MEpcq9iA',
                 'vu6PlPyKptsT6oEq50qOzA',
                 'FRpULkKmvD9caSKabQzq5w',
                 'ggGm83VrQAZS0um1uhiSEw',
                 'MaaySW1ejpwQCkr9jn1glA',
                 'zGYVSB7l73iv3Ue-48q63A',
                 '17Zv2e4Mh5I-wbp_x7WrpQ']
    
    if restaurant_data['hits']['total']['value'] > 0:
        data_list = restaurant_data['hits']['hits']
        random_list = list(map(lambda x: x['_id'], data_list))
    
    
    
    
    selected_restaurants = random.sample(random_list, k = 5)
    client = boto3.resource('dynamodb')
    
    x = client.batch_get_item(
        RequestItems={
            'yelp-restaurants': {'Keys': [{'business_id': id} for id in selected_restaurants]}
        }
    )
    # table = client.Table('yelp-restaurants-v2')
    
    # response = table.query(
    #     KeyConditionExpression = Key('business_id').eq(selected_restaurants)
    #     )
    
    SENDER = "Dining Concierge Bot <ab9114@nyu.edu>"


    RECIPIENT = data['email']
    
    AWS_REGION = "us-east-1"
    
    SUBJECT = "Restaurant Suggestions from Concierge"
    
    x = x['Responses']['yelp-restaurants']
    restaurant_str = []
    for i, res in enumerate(x):
        sent = "{}. {} located at {}".format(i+1, res['name'], res['address'])
        restaurant_str.append(sent)
        
    BODY_HTML = f"""<html>
    <head></head>
    <body>
      <p>Thank you for your patience. Here are our top picks for {data['cuisine']} cuisine & {data['num_of_people']} people are</p><br>
      <p>Restaurants:</p>
      <p>{restaurant_str[0]}</p>
      <p>{restaurant_str[1]}</p>
      <p>{restaurant_str[2]}</p>
      <p>{restaurant_str[3]}</p>
      <p>{restaurant_str[4]}</p>
    </body>
    </html>
    """
    
    # The character encoding for the email.
    CHARSET = "UTF-8"
    
    # Create a new SES resource and specify a region.
    client = boto3.client('ses', region_name=AWS_REGION)
    
    # Try to send the email.
    try:
        # Provide the contents of the email.
        response = client.send_email(
            Destination={
                'ToAddresses': [
                    RECIPIENT,
                ],
            },
            Message={
                'Body': {
                    'Html': {
                        'Charset': CHARSET,
                        'Data': BODY_HTML,
                    },
                    'Text': {
                        'Charset': CHARSET,
                        'Data': "Hello",
                    },
                },
                'Subject': {
                    'Charset': CHARSET,
                    'Data': SUBJECT,
                },
            },
            Source=SENDER,
        )
        
    # Display an error if something goes wrong.
    except Exception as e:
        print(e.response['Error']['Message'])
        
    else:
        print("Email sent! Message ID:"),
        print(response['MessageId'])
        
    client = boto3.client('sqs')
    client.delete_message(
        QueueUrl=QueueUrl,
        ReceiptHandle=receipt_handle
    )
    
                    
    return {
            'statusCode': 200,
            'body': x
            
        }
    