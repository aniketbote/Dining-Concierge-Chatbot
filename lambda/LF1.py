import json
import time
import datetime
import dateutil.parser
import os
import logging
import re
import boto3

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Helper functions
def safe_int(n):
    """
    Safely convert n value to int.
    """
    if n is not None:
        return int(n)
    return n

def try_ex(func):
    """
    Call passed in function in try block. If KeyError is encountered return None.
    This function is intended to be used to safely access dictionary.

    Note that this function would have negative impact on performance.
    """

    try:
        return func()
    except KeyError:
        return None
        
def close(session_attributes, fulfillment_state, message):
    response = {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Close',
            'fulfillmentState': fulfillment_state,
            'message': message
        }
    }
    return response
    
def elicit_slot(session_attributes, intent_name, slots, slot_to_elicit, message):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ElicitSlot',
            'intentName': intent_name,
            'slots': slots,
            'slotToElicit': slot_to_elicit,
            'message': message
        }
    }
    
def delegate(session_attributes, slots):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Delegate',
            'slots': slots
        }
    }
    
def isvalid_city(city):
    valid_cities = ['new york', 'los angeles', 'chicago', 'houston', 'philadelphia', 'phoenix', 'san antonio',
                    'san diego', 'dallas', 'san jose', 'austin', 'jacksonville', 'san francisco', 'indianapolis',
                    'columbus', 'fort worth', 'charlotte', 'detroit', 'el paso', 'seattle', 'denver', 'washington dc',
                    'memphis', 'boston', 'nashville', 'baltimore', 'portland']
    return city.lower() in valid_cities
    
def isvalid_date(date):
    try:
        dateutil.parser.parse(date)
        return True
    except ValueError:
        return False
        
def isvalid_cuisine_type(cuisine_type):
    cuisine_types = ['japanese', 'italian', 'american', 'chinese', 'mexican']
    return cuisine_type.lower() in cuisine_types
    
def build_validation_result(isvalid, violated_slot, message_content):
    return {
        'isValid': isvalid,
        'violatedSlot': violated_slot,
        'message': {'contentType': 'PlainText', 'content': message_content}
    }


def validate_send_suggestion(slots):
    location = try_ex(lambda: slots['location'])
    date = try_ex(lambda: slots['date'])
    cuisine = try_ex(lambda: slots['cuisine'])
    num_of_people = safe_int(try_ex(lambda: slots['num_of_people']))
    email = try_ex(lambda: slots['email'])

    if location and not isvalid_city(location):
        return build_validation_result(
            False,
            'location',
            'We currently do not support {} as a valid destination.  Can you try a different city?'.format(location)
        )
        

    if date:
        if not isvalid_date(date):
            return build_validation_result(False, 'date', 'I did not understand your date.  When would you like to make reservation?')
        
        if datetime.datetime.strptime(date, '%Y-%m-%d').date() <= datetime.date.today():
            return build_validation_result(False, 'date', 'Reservations must be scheduled at least one day in advance.  Can you try a different date?')

    
    if num_of_people is not None:
        if num_of_people > 10:
            return build_validation_result(
                False,
                'num_of_people',
                'We currently support reservation only for maximum 10 people?'
            )
        elif num_of_people <= 0:
            return build_validation_result(
                False,
                'num_of_people',
                'Please select valid number of people'
            )
            
    
    if cuisine is not None and not isvalid_cuisine_type(cuisine):
        return build_validation_result(
            False,
            'cuisine',
            f'We currently do not support reservations for {cuisine} cuisine. Please select from Japanese, Mexican, Italian, American, Chinese cuisines')
            
    if email is not None:
        regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        if not (re.fullmatch(regex, email)):
            return build_validation_result(
                False,
                'email',
                f'Please enter valid email number')

    return {'isValid': True}

# Intent functions
def send_suggestion(intent_request):
    slots = intent_request['currentIntent']['slots']
    location = slots['location']
    date = slots['date']
    cuisine = slots['cuisine']
    num_of_people = slots['num_of_people']
    email = slots['email']
    rtime = slots['rtime']
    
    confirmation_status = intent_request['currentIntent']['confirmationStatus']
    
    session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}

    # Load confirmation history and track the current reservation.
    reservation = json.dumps({
        'cuisine': cuisine,
        'location': location,
        'date': date,
        'num_of_people': num_of_people,
        'email': email,
        'rtime':rtime
    })
    
    session_attributes['currentReservation'] = reservation
    
    
    if intent_request['invocationSource'] == 'DialogCodeHook':
        # Validate any slots which have been specified.  If any are invalid, re-elicit for their value
        validation_result = validate_send_suggestion(intent_request['currentIntent']['slots'])
        if not validation_result['isValid']:
            slots[validation_result['violatedSlot']] = None
            return elicit_slot(
                session_attributes,
                intent_request['currentIntent']['name'],
                slots,
                validation_result['violatedSlot'],
                validation_result['message']
            )
        
        if confirmation_status == 'None':
            return delegate(session_attributes, intent_request['currentIntent']['slots'])
    
    # Booking the car.  In a real application, this would likely involve a call to a backend service.
    logger.debug('bookrestaurant at={}'.format(reservation))
    
    client = boto3.client('sqs')
    response = client.send_message(
        QueueUrl = 'https://sqs.us-east-1.amazonaws.com/227712325985/Q1',
        MessageBody = reservation
        )
    del session_attributes['currentReservation']
    
    return close(
        session_attributes,
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': 'You\'re all set. Expect my suggestions shortly! Have a good day.'
        }
    )
    

def send_greet(intent_request):
    return close(
        {},
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': 'Hi there, how can I help?'
        }
    )
    
def send_thanks(intent_request):
    return close(
        {},
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': 'It\'s my pleasure!'
        }
    )
    

# Function to select intent
def dispatch(intent_request):
    """
    Called when the user specifies an intent for this bot.
    """

    logger.debug('dispatch userId={}, intentName={}'.format(intent_request['userId'], intent_request['currentIntent']['name']))

    intent_name = intent_request['currentIntent']['name']

    # Dispatch to your bot's intent handlers
    if intent_name == 'GreetingIntent':
        return send_greet(intent_request)
    elif intent_name == 'DiningSuggestionsIntent':
        return send_suggestion(intent_request)
    elif intent_name == 'ThankYouIntent':
        return send_thanks(intent_request)

    raise Exception('Intent with name ' + intent_name + ' not supported')

# Main function
def lambda_handler(event, context):
    """
    Route the incoming request based on intent.
    The JSON body of the request is provided in the event slot.
    """
    # By default, treat the user request as coming from the America/New_York time zone.
    os.environ['TZ'] = 'America/New_York'
    time.tzset()
    logger.debug('event.bot.name={}'.format(event['bot']['name']))
    print('*' * 10)
    print(event)
    output = dispatch(event)
    print(output)
    print('$' * 10)
    return output
