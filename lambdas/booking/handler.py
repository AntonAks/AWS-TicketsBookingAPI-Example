import json
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

import boto3
from botocore.exceptions import ClientError
import redis

# Import from layer
from lib.db_utils import DynamoDBUtils
from lib.cache_utils import CacheUtils
from lib.validation import validate_booking_request, ValidationError
from lib.exceptions import BookingError, TicketNotAvailableError

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
sqs = boto3.client('sqs')
sns = boto3.client('sns')

# Environment variables
REGION = os.environ['AWS_REGION']
ENVIRONMENT = os.environ['ENVIRONMENT']
PROJECT_NAME = os.environ['PROJECT_NAME']

# Table names
EVENTS_TABLE = f"{PROJECT_NAME}-events-{ENVIRONMENT}"
BOOKINGS_TABLE = f"{PROJECT_NAME}-bookings-{ENVIRONMENT}"
TICKETS_TABLE = f"{PROJECT_NAME}-tickets-{ENVIRONMENT}"
USERS_TABLE = f"{PROJECT_NAME}-users-{ENVIRONMENT}"

# Queue URLs
BOOKING_QUEUE_URL = os.environ['BOOKING_QUEUE_URL']
PAYMENT_QUEUE_URL = os.environ['PAYMENT_QUEUE_URL']
NOTIFICATION_QUEUE_URL = os.environ['NOTIFICATION_QUEUE_URL']

# Redis connection
REDIS_ENDPOINT = os.environ.get('REDIS_ENDPOINT')
redis_client = redis.Redis.from_url(f"redis://{REDIS_ENDPOINT}:6379") if REDIS_ENDPOINT else None

# Initialize utilities
db_utils = DynamoDBUtils(dynamodb)
cache_utils = CacheUtils(redis_client)

# Constants
RESERVATION_TIMEOUT_MINUTES = 5
MAX_TICKETS_PER_USER = 6


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for booking operations
    """
    try:
        # Parse request
        http_method = event.get('httpMethod', '')
        path = event.get('path', '')
        body = json.loads(event.get('body', '{}')) if event.get('body') else {}
        query_params = event.get('queryStringParameters') or {}
        path_params = event.get('pathParameters') or {}

        # Get user from JWT token (set by authorizer)
        user_id = event.get('requestContext', {}).get('authorizer', {}).get('user_id')

        # Route to appropriate handler
        if http_method == 'POST' and path == '/booking/reserve':
            return reserve_tickets(body, user_id)
        elif http_method == 'POST' and path == '/booking/confirm':
            return confirm_booking(body, user_id)
        elif http_method == 'GET' and path.startswith('/booking/'):
            booking_id = path_params.get('booking_id')
            return get_booking(booking_id, user_id)
        elif http_method == 'DELETE' and path.startswith('/booking/'):
            booking_id = path_params.get('booking_id')
            return cancel_booking(booking_id, user_id)
        elif http_method == 'GET' and path == '/user/bookings':
            return get_user_bookings(user_id, query_params)
        else:
            return create_response(404, {'error': 'Endpoint not found'})

    except ValidationError as e:
        return create_response(400, {'error': str(e)})
    except BookingError as e:
        return create_response(409, {'error': str(e)})
    except TicketNotAvailableError as e:
        return create_response(409, {'error': str(e)})
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return create_response(500, {'error': 'Internal server error'})


def reserve_tickets(body: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Reserve tickets temporarily (5-minute hold)
    """
    # Validate request
    validate_booking_request(body)

    event_id = body['event_id']
    ticket_requests = body['tickets']  # [{'tier': 'vip', 'quantity': 2}]

    # Check if user has too many active bookings
    active_bookings = get_user_active_bookings_count(user_id)
    total_requested = sum(req['quantity'] for req in ticket_requests)

    if active_bookings + total_requested > MAX_TICKETS_PER_USER:
        raise BookingError(f"Maximum {MAX_TICKETS_PER_USER} tickets per user")

    # Get event details
    event = get_event(event_id)
    if not event or event['status'] != 'active':
        raise BookingError("Event not available for booking")

    # Start distributed lock for this event
    lock_key = f"booking_lock:{event_id}"
    with cache_utils.distributed_lock(lock_key, timeout=30):

        # Check ticket availability and reserve
        reserved_tickets = []
        total_amount = 0

        try:
            for ticket_request in ticket_requests:
                tier = ticket_request['tier']
                quantity = ticket_request['quantity']

                # Get available tickets for this tier
                available_tickets = get_available_tickets(event_id, tier, quantity)

                if len(available_tickets) < quantity:
                    raise TicketNotAvailableError(f"Only {len(available_tickets)} {tier} tickets available")

                # Reserve the tickets
                for i in range(quantity):
                    ticket = available_tickets[i]
                    ticket_id = ticket['ticket_id']

                    # Mark as reserved in DynamoDB
                    reservation_result = reserve_ticket_in_db(
                        event_id, ticket_id, user_id
                    )

                    if reservation_result:
                        reserved_tickets.append({
                            'ticket_id': ticket_id,
                            'tier': tier,
                            'price': ticket['price'],
                            'seat_number': ticket.get('seat_number', '')
                        })
                        total_amount += ticket['price']
                    else:
                        # Rollback previous reservations
                        rollback_reservations(reserved_tickets, user_id)
                        raise TicketNotAvailableError(f"Ticket {ticket_id} no longer available")

            # Create booking record
            booking_id = str(uuid.uuid4())
            reserved_until = datetime.utcnow() + timedelta(minutes=RESERVATION_TIMEOUT_MINUTES)

            booking = {
                'booking_id': booking_id,
                'user_id': user_id,
                'event_id': event_id,
                'tickets': reserved_tickets,
                'total_amount': total_amount,
                'status': 'reserved',
                'reserved_until': reserved_until.isoformat(),
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat(),
                'ttl': int(reserved_until.timestamp()) + 3600  # TTL 1 hour after reservation expires
            }

            # Save booking
            table = dynamodb.Table(BOOKINGS_TABLE)
            table.put_item(Item=booking)

            # Cache the booking
            cache_utils.set(f"booking:{booking_id}", booking, ttl=RESERVATION_TIMEOUT_MINUTES * 60)

            # Send to processing queue for async operations
            send_to_queue(BOOKING_QUEUE_URL, {
                'action': 'process_reservation',
                'booking_id': booking_id,
                'user_id': user_id
            })

            return create_response(201, {
                'booking_id': booking_id,
                'status': 'reserved',
                'reserved_until': reserved_until.isoformat(),
                'tickets': reserved_tickets,
                'total_amount': total_amount,
                'expires_in_minutes': RESERVATION_TIMEOUT_MINUTES
            })

        except Exception as e:
            # Rollback any reservations made
            rollback_reservations(reserved_tickets, user_id)
            raise e


def confirm_booking(body: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Confirm a reserved booking (moves to payment processing)
    """
    booking_id = body.get('booking_id')
    payment_method = body.get('payment_method', {})

    if not booking_id:
        raise ValidationError("booking_id is required")

    # Get booking
    booking = get_booking_by_id(booking_id)

    if not booking:
        raise BookingError("Booking not found")

    if booking['user_id'] != user_id:
        raise BookingError("Unauthorized access to booking")

    if booking['status'] != 'reserved':
        raise BookingError(f"Cannot confirm booking with status: {booking['status']}")

    # Check if reservation is still valid
    reserved_until = datetime.fromisoformat(booking['reserved_until'])
    if datetime.utcnow() > reserved_until:
        # Cancel expired booking
        cancel_booking_internal(booking_id)
        raise BookingError("Reservation has expired")

    # Update booking status to processing
    update_booking_status(booking_id, 'processing')

    # Send to payment queue
    send_to_queue(PAYMENT_QUEUE_URL, {
        'action': 'process_payment',
        'booking_id': booking_id,
        'user_id': user_id,
        'amount': booking['total_amount'],
        'payment_method': payment_method
    })

    return create_response(200, {
        'booking_id': booking_id,
        'status': 'processing',
        'message': 'Payment processing initiated'
    })


def get_booking(booking_id: str, user_id: str) -> Dict[str, Any]:
    """
    Get booking details
    """
    booking = get_booking_by_id(booking_id)

    if not booking:
        return create_response(404, {'error': 'Booking not found'})

    if booking['user_id'] != user_id:
        return create_response(403, {'error': 'Unauthorized access'})

    return create_response(200, booking)


def cancel_booking(booking_id: str, user_id: str) -> Dict[str, Any]:
    """
    Cancel a booking
    """
    booking = get_booking_by_id(booking_id)

    if not booking:
        return create_response(404, {'error': 'Booking not found'})

    if booking['user_id'] != user_id:
        return create_response(403, {'error': 'Unauthorized access'})

    if booking['status'] in ['cancelled', 'expired']:
        return create_response(409, {'error': 'Booking already cancelled'})

    if booking['status'] == 'confirmed':
        return create_response(409, {'error': 'Cannot cancel confirmed booking'})

    # Cancel the booking
    cancel_booking_internal(booking_id)

    return create_response(200, {'message': 'Booking cancelled successfully'})


def get_user_bookings(user_id: str, query_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get user's bookings with pagination
    """
    limit = int(query_params.get('limit', 20))
    last_key = query_params.get('last_key')
    status_filter = query_params.get('status')

    table = dynamodb.Table(BOOKINGS_TABLE)

    query_kwargs = {
        'IndexName': 'UserBookingsIndex',
        'KeyConditionExpression': 'user_id = :user_id',
        'ExpressionAttributeValues': {':user_id': user_id},
        'ScanIndexForward': False,  # Most recent first
        'Limit': limit
    }

    if last_key:
        query_kwargs['ExclusiveStartKey'] = json.loads(last_key)

    if status_filter:
        query_kwargs['FilterExpression'] = '#status = :status'
        query_kwargs['ExpressionAttributeNames'] = {'#status': 'status'}
        query_kwargs['ExpressionAttributeValues'][':status'] = status_filter

    response = table.query(**query_kwargs)

    result = {
        'bookings': response['Items'],
        'count': len(response['Items'])
    }

    if 'LastEvaluatedKey' in response:
        result['last_key'] = json.dumps(response['LastEvaluatedKey'])

    return create_response(200, result)


# Helper functions

def get_event(event_id: str) -> Optional[Dict[str, Any]]:
    """Get event details from cache or database"""
    # Try cache first
    cached_event = cache_utils.get(f"event:{event_id}")
    if cached_event:
        return cached_event

    # Get from database
    table = dynamodb.Table(EVENTS_TABLE)
    try:
        response = table.get_item(Key={'event_id': event_id})
        event = response.get('Item')

        # Cache for 5 minutes
        if event:
            cache_utils.set(f"event:{event_id}", event, ttl=300)

        return event
    except ClientError:
        return None


def get_available_tickets(event_id: str, tier: str, quantity: int) -> List[Dict[str, Any]]:
    """Get available tickets for specific tier"""
    table = dynamodb.Table(TICKETS_TABLE)

    response = table.query(
        IndexName='TicketStatusIndex',
        KeyConditionExpression='event_id = :event_id AND #status = :status',
        FilterExpression='tier = :tier',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={
            ':event_id': event_id,
            ':status': 'available',
            ':tier': tier
        },
        Limit=quantity * 2  # Get a few extra in case of race conditions
    )

    return response['Items']


def reserve_ticket_in_db(event_id: str, ticket_id: str, user_id: str) -> bool:
    """Reserve a ticket in the database using conditional write"""
    table = dynamodb.Table(TICKETS_TABLE)
    reserved_until = datetime.utcnow() + timedelta(minutes=RESERVATION_TIMEOUT_MINUTES)

    try:
        table.update_item(
            Key={'event_id': event_id, 'ticket_id': ticket_id},
            UpdateExpression='SET #status = :reserved, reserved_by = :user_id, reserved_until = :until',
            ConditionExpression='#status = :available',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':reserved': 'reserved',
                ':available': 'available',
                ':user_id': user_id,
                ':until': reserved_until.isoformat()
            }
        )
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            return False
        raise e


def rollback_reservations(reserved_tickets: List[Dict[str, Any]], user_id: str):
    """Rollback ticket reservations"""
    table = dynamodb.Table(TICKETS_TABLE)

    for ticket in reserved_tickets:
        try:
            table.update_item(
                Key={'event_id': ticket['event_id'], 'ticket_id': ticket['ticket_id']},
                UpdateExpression='SET #status = :available REMOVE reserved_by, reserved_until',
                ConditionExpression='reserved_by = :user_id',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':available': 'available',
                    ':user_id': user_id
                }
            )
        except ClientError:
            pass  # Best effort rollback


def get_user_active_bookings_count(user_id: str) -> int:
    """Get count of user's active bookings"""
    # Try cache first
    cached_count = cache_utils.get(f"user_bookings_count:{user_id}")
    if cached_count is not None:
        return int(cached_count)

    table = dynamodb.Table(BOOKINGS_TABLE)
    response = table.query(
        IndexName='UserBookingsIndex',
        KeyConditionExpression='user_id = :user_id',
        FilterExpression='#status IN (:reserved, :processing, :confirmed)',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={
            ':user_id': user_id,
            ':reserved': 'reserved',
            ':processing': 'processing',
            ':confirmed': 'confirmed'
        },
        Select='COUNT'
    )

    count = response['Count']

    # Cache for 1 minute
    cache_utils.set(f"user_bookings_count:{user_id}", count, ttl=60)

    return count


def get_booking_by_id(booking_id: str) -> Optional[Dict[str, Any]]:
    """Get booking by ID from cache or database"""
    # Try cache first
    cached_booking = cache_utils.get(f"booking:{booking_id}")
    if cached_booking:
        return cached_booking

    table = dynamodb.Table(BOOKINGS_TABLE)
    try:
        response = table.get_item(Key={'booking_id': booking_id})
        booking = response.get('Item')

        # Cache active bookings for 5 minutes
        if booking and booking['status'] in ['reserved', 'processing']:
            cache_utils.set(f"booking:{booking_id}", booking, ttl=300)

        return booking
    except ClientError:
        return None


def update_booking_status(booking_id: str, status: str):
    """Update booking status"""
    table = dynamodb.Table(BOOKINGS_TABLE)
    table.update_item(
        Key={'booking_id': booking_id},
        UpdateExpression='SET #status = :status, updated_at = :updated_at',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={
            ':status': status,
            ':updated_at': datetime.utcnow().isoformat()
        }
    )

    # Update cache
    booking = get_booking_by_id(booking_id)
    if booking:
        booking['status'] = status
        booking['updated_at'] = datetime.utcnow().isoformat()
        cache_utils.set(f"booking:{booking_id}", booking, ttl=300)


def cancel_booking_internal(booking_id: str):
    """Internal booking cancellation"""
    booking = get_booking_by_id(booking_id)
    if not booking:
        return

    # Release reserved tickets
    for ticket in booking['tickets']:
        release_ticket(booking['event_id'], ticket['ticket_id'])

    # Update booking status
    update_booking_status(booking_id, 'cancelled')

    # Clear cache
    cache_utils.delete(f"booking:{booking_id}")
    cache_utils.delete(f"user_bookings_count:{booking['user_id']}")


def release_ticket(event_id: str, ticket_id: str):
    """Release a reserved ticket back to available pool"""
    table = dynamodb.Table(TICKETS_TABLE)
    try:
        table.update_item(
            Key={'event_id': event_id, 'ticket_id': ticket_id},
            UpdateExpression='SET #status = :available REMOVE reserved_by, reserved_until',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':available': 'available'}
        )
    except ClientError:
        pass  # Best effort


def send_to_queue(queue_url: str, message: Dict[str, Any]):
    """Send message to SQS queue"""
    try:
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(message),
            MessageAttributes={
                'action': {
                    'StringValue': message.get('action', 'unknown'),
                    'DataType': 'String'
                }
            }
        )
    except ClientError as e:
        print(f"Failed to send message to queue {queue_url}: {str(e)}")


def create_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Create HTTP response"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
        },
        'body': json.dumps(body, default=str)
    }