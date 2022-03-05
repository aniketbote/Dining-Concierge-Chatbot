import json
from datetime import datetime
import boto3
import logging
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
client = boto3.client('lex-runtime')

def lambda_handler(event, context):
    logger.debug(event)
    
    text_type = event['messages'][0]['type']
    response = client.post_text(
        botName='DiningConcierge',
        botAlias ='$LATEST',
        userId="Aniket",
        inputText=event['messages'][0][text_type]['text']
        )
    return {
        'statusCode': 200,
        "messages": [
            {
                "type": "unstructured",
                "unstructured": {
                    "id": "Aniket",
                    "text": response['message'],
                    "timestamp": str(datetime.now())
                }
                
            }
        ]
    }
