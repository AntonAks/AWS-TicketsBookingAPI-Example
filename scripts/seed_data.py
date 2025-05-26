# scripts/seed_data.py

import boto3
import json
import uuid
import argparse
from datetime import datetime, timedelta
from decimal import Decimal
import random


class DatabaseSeeder:
    """Seed database with test data"""

    def __init__(self, environment: str, region: str = 'us-east-1'):
        self.environment = environment
        self.region = region
        self.project_name = 'ticket-booking'

        # Initialize DynamoDB
        if environment == 'local':
            self.dynamodb = boto3.resource(
                'dynamodb',
                endpoint_url='http://localhost:8000',
                region_name=region
            )
        else:
            self.dynamodb = boto3.resource('dynamodb', region_name=region)

        self.table_names = {
            'events': f"{self.project_name}-events-{environment}",
            'bookings': f"{self.project_name}-bookings-{environment}",
            'users': f"{self.project_name}-users-{environment}",
            'tickets': f"{self.project_name}-tickets-{environment}",
            'sessions': f"{self.project_name}-sessions-{environment}",
            'analytics': f"{self.project_name}-analytics-{environment}"
        }

    def create_tables_if_not_exist(self):
        """Create DynamoDB tables if they don't exist (for local development)"""
        if self.environment != 'local':
            print("Skipping table creation for non-local environment")
            return

        # Events table
        try:
            self.dynamodb.create_table(
                TableName=self.table_names['events'],
                KeySchema=[{'AttributeName': 'event_id', 'KeyType': 'HASH'}],
                AttributeDefinitions=[
                    {'AttributeName': 'event_id', 'AttributeType': 'S'},
                    {'AttributeName': 'status', 'AttributeType': 'S'},
                    {'AttributeName': 'date', 'AttributeType': 'S'}
                ],
                GlobalSecondaryIndexes=[{
                    'IndexName': 'StatusDateIndex',
                    'KeySchema': [
                        {'AttributeName': 'status', 'KeyType': 'HASH'},
                        {'AttributeName': 'date', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
                }],
                BillingMode='PROVISIONED',
                ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
            )
            print(f"Created table: {self.table_names['events']}")
        except Exception as e:
            print(f"Events table may already exist: {str(e)}")

        # Bookings table
        try:
            self.dynamodb.create_table(
                TableName=self.table_names['bookings'],
                KeySchema=[{'AttributeName': 'booking_id', 'KeyType': 'HASH'}],
                AttributeDefinitions=[
                    {'AttributeName': 'booking_id', 'AttributeType': 'S'},
                    {'AttributeName': 'user_id', 'AttributeType': 'S'},
                    {'AttributeName': 'event_id', 'AttributeType': 'S'},
                    {'AttributeName': 'status', 'AttributeType': 'S'},
                    {'AttributeName': 'created_at', 'AttributeType': 'S'}
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'UserBookingsIndex',
                        'KeySchema': [
                            {'AttributeName': 'user_id', 'KeyType': 'HASH'},
                            {'AttributeName': 'created_at', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
                    },
                    {
                        'IndexName': 'EventBookingsIndex',
                        'KeySchema': [
                            {'AttributeName': 'event_id', 'KeyType': 'HASH'},
                            {'AttributeName': 'status', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
                    }
                ],
                BillingMode='PROVISIONED',
                ProvisionedThroughput={'ReadCapacityUnits': 10, 'WriteCapacityUnits': 10}
            )
            print(f"Created table: {self.table_names['bookings']}")
        except Exception as e:
            print(f"Bookings table may already exist: {str(e)}")

        # Users table
        try:
            self.dynamodb.create_table(
                TableName=self.table_names['users'],
                KeySchema=[{'AttributeName': 'user_id', 'KeyType': 'HASH'}],
                AttributeDefinitions=[
                    {'AttributeName': 'user_id', 'AttributeType': 'S'},
                    {'AttributeName': 'email', 'AttributeType': 'S'}
                ],
                GlobalSecondaryIndexes=[{
                    'IndexName': 'EmailIndex',
                    'KeySchema': [{'AttributeName': 'email', 'KeyType': 'HASH'}],
                    'Projection': {'ProjectionType': 'ALL'},
                    'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
                }],
                BillingMode='PROVISIONED',
                ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
            )
            print(f"Created table: {self.table_names['users']}")
        except Exception as e:
            print(f"Users table may already exist: {str(e)}")

        # Tickets table
        try:
            self.dynamodb.create_table(
                TableName=self.table_names['tickets'],
                KeySchema=[
                    {'AttributeName': 'event_id', 'KeyType': 'HASH'},
                    {'AttributeName': 'ticket_id', 'KeyType': 'RANGE'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'event_id', 'AttributeType': 'S'},
                    {'AttributeName': 'ticket_id', 'AttributeType': 'S'},
                    {'AttributeName': 'status', 'AttributeType': 'S'},
                    {'AttributeName': 'tier', 'AttributeType': 'S'}
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'TicketStatusIndex',
                        'KeySchema': [
                            {'AttributeName': 'event_id', 'KeyType': 'HASH'},
                            {'AttributeName': 'status', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {'ReadCapacityUnits': 10, 'WriteCapacityUnits': 10}
                    },
                    {
                        'IndexName': 'TicketTierIndex',
                        'KeySchema': [
                            {'AttributeName': 'event_id', 'KeyType': 'HASH'},
                            {'AttributeName': 'tier', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {'ReadCapacityUnits': 10, 'WriteCapacityUnits': 10}
                    }
                ],
                BillingMode='PROVISIONED',
                ProvisionedThroughput={'ReadCapacityUnits': 20, 'WriteCapacityUnits': 20}
            )
            print(f"Created table: {self.table_names['tickets']}")
        except Exception as e:
            print(f"Tickets table may already exist: {str(e)}")

    def seed_events(self):
        """Seed events data"""
        print("Seeding events...")

        events = [
            {
                'event_id': 'event-1',
                'name': 'Rock Concert 2025',
                'description': 'Amazing rock concert with top artists',
                'venue': 'Madison Square Garden',
                'venue_address': '4 Pennsylvania Plaza, New York, NY 10001',
                'date': (datetime.utcnow() + timedelta(days=30)).isoformat(),
                'doors_open': '19:00',
                'show_start': '20:00',
                'total_tickets': 1600,
                'available_tickets': 1600,
                'price_tiers': {
                    'vip': {'price': Decimal('200'), 'available': 100, 'total': 100},
                    'premium': {'price': Decimal('100'), 'available': 500, 'total': 500},
                    'standard': {'price': Decimal('50'), 'available': 1000, 'total': 1000}
                },
                'status': 'active',
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat(),
                'genre': 'Rock',
                'age_restriction': '18+',
                'organizer': 'Rock Events Inc.'
            },
            {
                'event_id': 'event-2',
                'name': 'Jazz Night 2025',
                'description': 'Intimate jazz performance',
                'venue': 'Blue Note',
                'venue_address': '131 W 3rd St, New York, NY 10012',
                'date': (datetime.utcnow() + timedelta(days=45)).isoformat(),
                'doors_open': '19:30',
                'show_start': '20:30',
                'total_tickets': 300,
                'available_tickets': 300,
                'price_tiers': {
                    'vip': {'price': Decimal('150'), 'available': 50, 'total': 50},
                    'premium': {'price': Decimal('80'), 'available': 100, 'total': 100},
                    'standard': {'price': Decimal('40'), 'available': 150, 'total': 150}
                },
                'status': 'active',
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat(),
                'genre': 'Jazz',
                'age_restriction': '21+',
                'organizer': 'Jazz Productions'
            },
            {
                'event_id': 'event-3',
                'name': 'Electronic Music Festival',
                'description': 'Three-day electronic music festival',
                'venue': 'Central Park',
                'venue_address': 'Central Park, New York, NY',
                'date': (datetime.utcnow() + timedelta(days=60)).isoformat(),
                'doors_open': '12:00',
                'show_start': '13:00',
                'total_tickets': 5000,
                'available_tickets': 5000,
                'price_tiers': {
                    'vip': {'price': Decimal('400'), 'available': 200, 'total': 200},
                    'premium': {'price': Decimal('200'), 'available': 800, 'total': 800},
                    'standard': {'price': Decimal('100'), 'available': 4000, 'total': 4000}
                },
                'status': 'active',
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat(),
                'genre': 'Electronic',
                'age_restriction': '18+',
                'organizer': 'Festival Organizers LLC'
            },
            {
                'event_id': 'event-4',
                'name': 'Classical Symphony',
                'description': 'Beautiful classical music performance',
                'venue': 'Carnegie Hall',
                'venue_address': '881 7th Ave, New York, NY 10019',
                'date': (datetime.utcnow() + timedelta(days=15)).isoformat(),
                'doors_open': '19:00',
                'show_start': '19:30',
                'total_tickets': 800,
                'available_tickets': 800,
                'price_tiers': {
                    'vip': {'price': Decimal('250'), 'available': 100, 'total': 100},
                    'premium': {'price': Decimal('120'), 'available': 300, 'total': 300},
                    'standard': {'price': Decimal('60'), 'available': 400, 'total': 400}
                },
                'status': 'active',
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat(),
                'genre': 'Classical',
                'age_restriction': 'All Ages',
                'organizer': 'Classical Music Society'
            },
            {
                'event_id': 'event-5',
                'name': 'Comedy Show - SOLD OUT',
                'description': 'Hilarious comedy show',
                'venue': 'Comedy Cellar',
                'venue_address': '117 MacDougal St, New York, NY 10012',
                'date': (datetime.utcnow() + timedelta(days=7)).isoformat(),
                'doors_open': '19:00',
                'show_start': '20:00',
                'total_tickets': 200,
                'available_tickets': 0,
                'price_tiers': {
                    'vip': {'price': Decimal('80'), 'available': 0, 'total': 50},
                    'standard': {'price': Decimal('40'), 'available': 0, 'total': 150}
                },
                'status': 'sold_out',
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat(),
                'genre': 'Comedy',
                'age_restriction': '18+',
                'organizer': 'Laugh Factory'
            }
        ]

        table = self.dynamodb.Table(self.table_names['events'])

        with table.batch_writer() as batch:
            for event in events:
                batch.put_item(Item=event)

        print(f"Seeded {len(events)} events")
        return events

    def seed_tickets(self, events):
        """Seed tickets for each event"""
        print("Seeding tickets...")

        table = self.dynamodb.Table(self.table_names['tickets'])

        total_tickets = 0

        for event in events:
            event_id = event['event_id']

            # Generate tickets for each tier
            for tier, tier_info in event['price_tiers'].items():
                tier_count = int(tier_info['total'])

                for i in range(tier_count):
                    ticket_id = f"{event_id}-{tier}-{i + 1:04d}"

                    # Generate seat number (simplified)
                    section = random.choice(['A', 'B', 'C', 'D'])
                    row = random.randint(1, 20)
                    seat = random.randint(1, 30)
                    seat_number = f"{section}{row:02d}-{seat:02d}"

                    ticket = {
                        'event_id': event_id,
                        'ticket_id': ticket_id,
                        'tier': tier,
                        'seat_number': seat_number,
                        'price': tier_info['price'],
                        'status': 'available',
                        'created_at': datetime.utcnow().isoformat()
                    }

                    # Some tickets are already sold for the sold out event
                    if event['status'] == 'sold_out':
                        ticket['status'] = 'sold'
                        ticket['sold_to'] = f'user-{random.randint(1, 100)}'
                        ticket['sold_at'] = (datetime.utcnow() - timedelta(days=random.randint(1, 30))).isoformat()

                    table.put_item(Item=ticket)
                    total_tickets += 1

        print(f"Seeded {total_tickets} tickets")

    def seed_users(self):
        """Seed test users"""
        print("Seeding users...")

        users = [
            {
                'user_id': 'user-1',
                'email': 'john.doe@example.com',
                'name': 'John Doe',
                'phone': '+1555000001',
                'password_hash': 'hashed_password_1',  # In real app, this would be properly hashed
                'total_bookings': 0,
                'created_at': datetime.utcnow().isoformat(),
                'status': 'active',
                'preferences': {
                    'email_notifications': True,
                    'sms_notifications': False,
                    'preferred_genres': ['Rock', 'Jazz']
                }
            },
            {
                'user_id': 'user-2',
                'email': 'jane.smith@example.com',
                'name': 'Jane Smith',
                'phone': '+1555000002',
                'password_hash': 'hashed_password_2',
                'total_bookings': 0,
                'created_at': datetime.utcnow().isoformat(),
                'status': 'active',
                'preferences': {
                    'email_notifications': True,
                    'sms_notifications': True,
                    'preferred_genres': ['Classical', 'Jazz']
                }
            },
            {
                'user_id': 'user-3',
                'email': 'mike.johnson@example.com',
                'name': 'Mike Johnson',
                'phone': '+1555000003',
                'password_hash': 'hashed_password_3',
                'total_bookings': 0,
                'created_at': datetime.utcnow().isoformat(),
                'status': 'active',
                'preferences': {
                    'email_notifications': False,
                    'sms_notifications': True,
                    'preferred_genres': ['Electronic', 'Rock']
                }
            },
            {
                'user_id': 'load-test-user',
                'email': 'loadtest@example.com',
                'name': 'Load Test User',
                'phone': '+1555999999',
                'password_hash': 'hashed_load_test_password',
                'total_bookings': 0,
                'created_at': datetime.utcnow().isoformat(),
                'status': 'active',
                'preferences': {
                    'email_notifications': False,
                    'sms_notifications': False,
                    'preferred_genres': ['All']
                }
            }
        ]

        table = self.dynamodb.Table(self.table_names['users'])

        with table.batch_writer() as batch:
            for user in users:
                batch.put_item(Item=user)

        print(f"Seeded {len(users)} users")
        return users

    def seed_sample_bookings(self, events, users):
        """Seed some sample bookings"""
        print("Seeding sample bookings...")

        bookings = []

        # Create some confirmed bookings
        for i in range(5):
            user = random.choice(users)
            event = random.choice([e for e in events if e['status'] == 'active'])

            # Choose random tier
            available_tiers = [tier for tier, info in event['price_tiers'].items() if info['available'] > 0]
            if not available_tiers:
                continue

            tier = random.choice(available_tiers)
            quantity = random.randint(1, min(3, event['price_tiers'][tier]['available']))

            booking_id = str(uuid.uuid4())

            # Generate tickets for this booking
            tickets = []
            total_amount = 0
            for j in range(quantity):
                ticket_id = f"{event['event_id']}-{tier}-{random.randint(1, 1000):04d}"
                tickets.append({
                    'ticket_id': ticket_id,
                    'tier': tier,
                    'price': float(event['price_tiers'][tier]['price']),
                    'seat_number': f"A{random.randint(1, 20):02d}-{random.randint(1, 30):02d}"
                })
                total_amount += float(event['price_tiers'][tier]['price'])

            created_date = datetime.utcnow() - timedelta(days=random.randint(1, 10))

            booking = {
                'booking_id': booking_id,
                'user_id': user['user_id'],
                'event_id': event['event_id'],
                'tickets': tickets,
                'total_amount': Decimal(str(total_amount)),
                'status': 'confirmed',
                'created_at': created_date.isoformat(),
                'updated_at': created_date.isoformat(),
                'confirmed_at': (created_date + timedelta(minutes=random.randint(5, 30))).isoformat(),
                'payment_id': str(uuid.uuid4()),
                'payment_method': 'credit_card',
                'booking_reference': f'TB{random.randint(100000, 999999)}'
            }

            bookings.append(booking)

        # Create some reserved bookings (not yet confirmed)
        for i in range(3):
            user = random.choice(users)
            event = random.choice([e for e in events if e['status'] == 'active'])

            available_tiers = [tier for tier, info in event['price_tiers'].items() if info['available'] > 0]
            if not available_tiers:
                continue

            tier = random.choice(available_tiers)
            quantity = random.randint(1, 2)

            booking_id = str(uuid.uuid4())

            tickets = []
            total_amount = 0
            for j in range(quantity):
                ticket_id = f"{event['event_id']}-{tier}-{random.randint(1, 1000):04d}"
                tickets.append({
                    'ticket_id': ticket_id,
                    'tier': tier,
                    'price': float(event['price_tiers'][tier]['price']),
                    'seat_number': f"B{random.randint(1, 20):02d}-{random.randint(1, 30):02d}"
                })
                total_amount += float(event['price_tiers'][tier]['price'])

            created_date = datetime.utcnow() - timedelta(minutes=random.randint(1, 30))
            reserved_until = created_date + timedelta(minutes=5)

            booking = {
                'booking_id': booking_id,
                'user_id': user['user_id'],
                'event_id': event['event_id'],
                'tickets': tickets,
                'total_amount': Decimal(str(total_amount)),
                'status': 'reserved',
                'created_at': created_date.isoformat(),
                'updated_at': created_date.isoformat(),
                'reserved_until': reserved_until.isoformat(),
                'ttl': int((reserved_until + timedelta(hours=1)).timestamp())
            }

            bookings.append(booking)

        table = self.dynamodb.Table(self.table_names['bookings'])

        with table.batch_writer() as batch:
            for booking in bookings:
                batch.put_item(Item=booking)

        print(f"Seeded {len(bookings)} sample bookings")

    def seed_analytics_data(self):
        """Seed some analytics data"""
        print("Seeding analytics data...")

        analytics_data = []

        # Generate daily booking metrics for the past 30 days
        for i in range(30):
            date = datetime.utcnow() - timedelta(days=i)

            # Booking metrics
            analytics_data.append({
                'metric_type': 'daily_bookings',
                'timestamp': date.strftime('%Y-%m-%d'),
                'value': Decimal(str(random.randint(10, 100))),
                'metadata': {
                    'confirmed': random.randint(8, 80),
                    'cancelled': random.randint(1, 10),
                    'revenue': random.randint(1000, 10000)
                },
                'ttl': int((date + timedelta(days=365)).timestamp())  # Keep for 1 year
            })

            # Revenue metrics
            analytics_data.append({
                'metric_type': 'daily_revenue',
                'timestamp': date.strftime('%Y-%m-%d'),
                'value': Decimal(str(random.randint(5000, 50000))),
                'metadata': {
                    'vip_revenue': random.randint(2000, 20000),
                    'premium_revenue': random.randint(2000, 20000),
                    'standard_revenue': random.randint(1000, 10000)
                },
                'ttl': int((date + timedelta(days=365)).timestamp())
            })

        # Generate hourly metrics for today
        for hour in range(24):
            timestamp = datetime.utcnow().replace(hour=hour, minute=0, second=0, microsecond=0)

            analytics_data.append({
                'metric_type': 'hourly_traffic',
                'timestamp': timestamp.isoformat(),
                'value': Decimal(str(random.randint(10, 500))),
                'metadata': {
                    'api_calls': random.randint(100, 1000),
                    'unique_users': random.randint(50, 200),
                    'errors': random.randint(0, 10)
                },
                'ttl': int((timestamp + timedelta(days=30)).timestamp())  # Keep for 30 days
            })

        table = self.dynamodb.Table(self.table_names['analytics'])

        with table.batch_writer() as batch:
            for data in analytics_data:
                batch.put_item(Item=data)

        print(f"Seeded {len(analytics_data)} analytics records")

    def verify_seeded_data(self):
        """Verify that data was seeded correctly"""
        print("\nVerifying seeded data...")

        try:
            # Check events
            events_table = self.dynamodb.Table(self.table_names['events'])
            events_response = events_table.scan()
            events_count = events_response['Count']
            print(f"✓ Events: {events_count} records")

            # Check users
            users_table = self.dynamodb.Table(self.table_names['users'])
            users_response = users_table.scan()
            users_count = users_response['Count']
            print(f"✓ Users: {users_count} records")

            # Check tickets
            tickets_table = self.dynamodb.Table(self.table_names['tickets'])
            tickets_response = tickets_table.scan(Select='COUNT')
            tickets_count = tickets_response['Count']
            print(f"✓ Tickets: {tickets_count} records")

            # Check bookings
            bookings_table = self.dynamodb.Table(self.table_names['bookings'])
            bookings_response = bookings_table.scan()
            bookings_count = bookings_response['Count']
            print(f"✓ Bookings: {bookings_count} records")

            # Check analytics
            analytics_table = self.dynamodb.Table(self.table_names['analytics'])
            analytics_response = analytics_table.scan(Select='COUNT')
            analytics_count = analytics_response['Count']
            print(f"✓ Analytics: {analytics_count} records")

            print(f"\n✅ Data seeding completed successfully!")
            print(
                f"Total records created: {events_count + users_count + tickets_count + bookings_count + analytics_count}")

        except Exception as e:
            print(f"❌ Error verifying data: {str(e)}")

    def clean_all_data(self):
        """Clean all data from tables (for testing)"""
        print("🧹 Cleaning all data...")

        for table_name in self.table_names.values():
            try:
                table = self.dynamodb.Table(table_name)

                # Scan and delete all items
                response = table.scan()

                with table.batch_writer() as batch:
                    for item in response['Items']:
                        # Get the key for this item
                        key = {}

                        if table_name.endswith('events'):
                            key = {'event_id': item['event_id']}
                        elif table_name.endswith('users'):
                            key = {'user_id': item['user_id']}
                        elif table_name.endswith('bookings'):
                            key = {'booking_id': item['booking_id']}
                        elif table_name.endswith('tickets'):
                            key = {'event_id': item['event_id'], 'ticket_id': item['ticket_id']}
                        elif table_name.endswith('sessions'):
                            key = {'session_id': item['session_id']}
                        elif table_name.endswith('analytics'):
                            key = {'metric_type': item['metric_type'], 'timestamp': item['timestamp']}

                        batch.delete_item(Key=key)

                print(f"✓ Cleaned table: {table_name}")

            except Exception as e:
                print(f"❌ Error cleaning table {table_name}: {str(e)}")

    def run_full_seed(self):
        """Run complete data seeding process"""
        print("🌱 Starting full database seeding...")

        # Create tables for local development
        if self.environment == 'local':
            self.create_tables_if_not_exist()

            # Wait for tables to be created
            import time
            print("Waiting for tables to be ready...")
            time.sleep(5)

        # Seed data
        events = self.seed_events()
        users = self.seed_users()
        self.seed_tickets(events)
        self.seed_sample_bookings(events, users)
        self.seed_analytics_data()

        # Verify
        self.verify_seeded_data()


def main():
    parser = argparse.ArgumentParser(description='Seed ticket booking database')
    parser.add_argument('--environment', '-e', default='local',
                        choices=['local', 'dev', 'staging', 'prod'],
                        help='Environment to seed')
    parser.add_argument('--region', '-r', default='us-east-1',
                        help='AWS region')
    parser.add_argument('--clean', action='store_true',
                        help='Clean all data before seeding')
    parser.add_argument('--verify-only', action='store_true',
                        help='Only verify existing data')

    args = parser.parse_args()

    if args.environment == 'prod':
        confirmation = input("⚠️  You are about to seed PRODUCTION data. Type 'YES' to continue: ")
        if confirmation != 'YES':
            print("Aborted.")
            return

    seeder = DatabaseSeeder(args.environment, args.region)

    try:
        if args.verify_only:
            seeder.verify_seeded_data()
        elif args.clean:
            seeder.clean_all_data()
            seeder.run_full_seed()
        else:
            seeder.run_full_seed()

    except KeyboardInterrupt:
        print("\n⏹️  Seeding interrupted by user")
    except Exception as e:
        print(f"❌ Error during seeding: {str(e)}")
        raise


if __name__ == "__main__":
    main()