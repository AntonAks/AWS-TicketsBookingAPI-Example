# load-generator/generator.py

import asyncio
import aiohttp
import json
import os
import time
import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import yaml
import argparse
import statistics


@dataclass
class TestConfig:
    api_base_url: str
    concurrent_users: int
    test_duration_minutes: int
    requests_per_second: int
    scenario: str
    ramp_up_seconds: int = 60
    ramp_down_seconds: int = 30


@dataclass
class TestResult:
    timestamp: float
    method: str
    endpoint: str
    status_code: int
    response_time: float
    success: bool
    error: Optional[str] = None


class TicketBookingLoadGenerator:
    def __init__(self, config: TestConfig):
        self.config = config
        self.results: List[TestResult] = []
        self.users: List[Dict[str, Any]] = []
        self.events: List[Dict[str, Any]] = []
        self.active_bookings: Dict[str, Dict] = {}
        self.session: Optional[aiohttp.ClientSession] = None

    async def setup(self):
        """Setup test environment"""
        print(f"Setting up load test with {self.config.concurrent_users} users...")

        # Create HTTP session with connection pooling
        connector = aiohttp.TCPConnector(
            limit=self.config.concurrent_users * 2,
            limit_per_host=self.config.concurrent_users,
            keepalive_timeout=30
        )

        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={'Content-Type': 'application/json'}
        )

        # Generate test users
        await self.generate_test_users()

        # Get available events
        await self.fetch_events()

        print(f"Setup complete: {len(self.users)} users, {len(self.events)} events")

    async def generate_test_users(self):
        """Generate test users and register them"""
        print("Generating test users...")

        for i in range(self.config.concurrent_users):
            user_data = {
                'email': f'testuser{i}@example.com',
                'name': f'Test User {i}',
                'phone': f'+1555000{i:04d}',
                'password': 'testpassword123'
            }

            # Register user
            async with self.session.post(
                    f"{self.config.api_base_url}/auth/register",
                    json=user_data
            ) as resp:
                if resp.status == 201:
                    user_result = await resp.json()

                    # Login to get token
                    login_data = {
                        'email': user_data['email'],
                        'password': user_data['password']
                    }

                    async with self.session.post(
                            f"{self.config.api_base_url}/auth/login",
                            json=login_data
                    ) as login_resp:
                        if login_resp.status == 200:
                            login_result = await login_resp.json()
                            self.users.append({
                                'user_id': user_result['user_id'],
                                'email': user_data['email'],
                                'token': login_result['token'],
                                'headers': {'Authorization': f"Bearer {login_result['token']}"}
                            })
                        else:
                            print(f"Failed to login user {i}: {login_resp.status}")
                else:
                    print(f"Failed to register user {i}: {resp.status}")

    async def fetch_events(self):
        """Fetch available events for testing"""
        print("Fetching available events...")

        async with self.session.get(
                f"{self.config.api_base_url}/events"
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                self.events = [e for e in data.get('events', []) if e['status'] == 'active']
            else:
                print(f"Failed to fetch events: {resp.status}")
                # Create mock events for testing
                self.events = [
                    {
                        'event_id': 'test-event-1',
                        'name': 'Load Test Concert 1',
                        'venue': 'Test Arena',
                        'date': (datetime.utcnow() + timedelta(days=30)).isoformat(),
                        'price_tiers': {
                            'standard': {'price': 50, 'available': 1000},
                            'premium': {'price': 100, 'available': 500},
                            'vip': {'price': 200, 'available': 100}
                        }
                    }
                ]

    async def run_test(self):
        """Run the load test"""
        print(f"Starting {self.config.scenario} test...")
        print(f"Duration: {self.config.test_duration_minutes} minutes")
        print(f"Concurrent users: {self.config.concurrent_users}")
        print(f"Requests per second: {self.config.requests_per_second}")

        start_time = time.time()
        end_time = start_time + (self.config.test_duration_minutes * 60)

        # Create user tasks
        tasks = []
        for i, user in enumerate(self.users):
            # Stagger user start times for ramp-up
            delay = (i / len(self.users)) * self.config.ramp_up_seconds
            task = asyncio.create_task(
                self.user_scenario(user, start_time + delay, end_time)
            )
            tasks.append(task)

        # Wait for all tasks to complete
        await asyncio.gather(*tasks, return_exceptions=True)

        print(f"Test completed in {time.time() - start_time:.2f} seconds")

    async def user_scenario(self, user: Dict[str, Any], start_time: float, end_time: float):
        """Run scenario for a single user"""
        # Wait for user's start time
        await asyncio.sleep(max(0, start_time - time.time()))

        scenario_func = getattr(self, f"scenario_{self.config.scenario}", None)
        if not scenario_func:
            scenario_func = self.scenario_mixed

        await scenario_func(user, end_time)

    async def scenario_basic_booking(self, user: Dict[str, Any], end_time: float):
        """Basic booking scenario: browse events, reserve, confirm, cancel"""
        while time.time() < end_time:
            try:
                # Browse events (20% of requests)
                if random.random() < 0.2:
                    await self.browse_events(user)

                # Reserve tickets (40% of requests)
                elif random.random() < 0.6:
                    await self.reserve_tickets(user)

                # Confirm booking (20% of requests)
                elif random.random() < 0.8:
                    await self.confirm_booking(user)

                # Cancel booking (10% of requests)
                else:
                    await self.cancel_booking(user)

                # Check my bookings (10% of requests)
                if random.random() < 0.1:
                    await self.get_user_bookings(user)

                # Wait between requests
                await asyncio.sleep(random.uniform(1, 3))

            except Exception as e:
                print(f"Error in user scenario: {str(e)}")

    async def scenario_concurrent_booking(self, user: Dict[str, Any], end_time: float):
        """Concurrent booking scenario: high contention for same tickets"""
        target_event = random.choice(self.events)

        while time.time() < end_time:
            try:
                # Focus on one event to create contention
                await self.reserve_tickets(user, target_event['event_id'])
                await asyncio.sleep(random.uniform(0.1, 0.5))

            except Exception as e:
                print(f"Error in concurrent booking: {str(e)}")

    async def scenario_stress_test(self, user: Dict[str, Any], end_time: float):
        """Stress test scenario: maximum load"""
        while time.time() < end_time:
            try:
                # Random actions with minimal delays
                action = random.choice([
                    self.browse_events,
                    self.reserve_tickets,
                    self.get_user_bookings
                ])
                await action(user)
                await asyncio.sleep(random.uniform(0.1, 0.3))

            except Exception as e:
                print(f"Error in stress test: {str(e)}")

    async def scenario_mixed(self, user: Dict[str, Any], end_time: float):
        """Mixed scenario: realistic user behavior"""
        while time.time() < end_time:
            try:
                # Simulate realistic user session
                await self.browse_events(user)
                await asyncio.sleep(random.uniform(2, 5))

                if random.random() < 0.3:  # 30% chance to book
                    booking_id = await self.reserve_tickets(user)
                    if booking_id:
                        await asyncio.sleep(random.uniform(10, 30))  # Think time

                        if random.random() < 0.8:  # 80% confirm, 20% cancel
                            await self.confirm_booking_by_id(user, booking_id)
                        else:
                            await self.cancel_booking_by_id(user, booking_id)

                await asyncio.sleep(random.uniform(5, 15))  # Session gap

            except Exception as e:
                print(f"Error in mixed scenario: {str(e)}")

    # API call methods

    async def browse_events(self, user: Dict[str, Any]):
        """Browse available events"""
        start_time = time.time()
        try:
            async with self.session.get(
                    f"{self.config.api_base_url}/events",
                    headers=user['headers']
            ) as resp:
                response_time = time.time() - start_time
                success = resp.status == 200

                self.results.append(TestResult(
                    timestamp=start_time,
                    method='GET',
                    endpoint='/events',
                    status_code=resp.status,
                    response_time=response_time,
                    success=success
                ))

                if success:
                    data = await resp.json()
                    return data.get('events', [])

        except Exception as e:
            response_time = time.time() - start_time
            self.results.append(TestResult(
                timestamp=start_time,
                method='GET',
                endpoint='/events',
                status_code=0,
                response_time=response_time,
                success=False,
                error=str(e)
            ))

    async def reserve_tickets(self, user: Dict[str, Any], event_id: str = None) -> Optional[str]:
        """Reserve tickets for an event"""
        if not event_id:
            event = random.choice(self.events)
            event_id = event['event_id']
        else:
            event = next((e for e in self.events if e['event_id'] == event_id), None)
            if not event:
                return None

        # Select random tier and quantity
        tiers = list(event['price_tiers'].keys())
        tier = random.choice(tiers)
        quantity = random.randint(1, min(4, event['price_tiers'][tier]['available']))

        booking_data = {
            'event_id': event_id,
            'tickets': [{'tier': tier, 'quantity': quantity}]
        }

        start_time = time.time()
        try:
            async with self.session.post(
                    f"{self.config.api_base_url}/booking/reserve",
                    json=booking_data,
                    headers=user['headers']
            ) as resp:
                response_time = time.time() - start_time
                success = resp.status == 201

                self.results.append(TestResult(
                    timestamp=start_time,
                    method='POST',
                    endpoint='/booking/reserve',
                    status_code=resp.status,
                    response_time=response_time,
                    success=success
                ))

                if success:
                    data = await resp.json()
                    booking_id = data['booking_id']
                    self.active_bookings[booking_id] = {
                        'user_id': user['user_id'],
                        'booking_id': booking_id,
                        'status': 'reserved'
                    }
                    return booking_id

        except Exception as e:
            response_time = time.time() - start_time
            self.results.append(TestResult(
                timestamp=start_time,
                method='POST',
                endpoint='/booking/reserve',
                status_code=0,
                response_time=response_time,
                success=False,
                error=str(e)
            ))

        return None

    async def confirm_booking(self, user: Dict[str, Any]) -> bool:
        """Confirm a random user booking"""
        user_bookings = [b for b in self.active_bookings.values()
                         if b['user_id'] == user['user_id'] and b['status'] == 'reserved']

        if not user_bookings:
            return False

        booking = random.choice(user_bookings)
        return await self.confirm_booking_by_id(user, booking['booking_id'])

    async def confirm_booking_by_id(self, user: Dict[str, Any], booking_id: str) -> bool:
        """Confirm specific booking"""
        confirm_data = {
            'booking_id': booking_id,
            'payment_method': {
                'type': 'credit_card',
                'card_number': '4111111111111111',
                'expiry': '12/25',
                'cvv': '123'
            }
        }

        start_time = time.time()
        try:
            async with self.session.post(
                    f"{self.config.api_base_url}/booking/confirm",
                    json=confirm_data,
                    headers=user['headers']
            ) as resp:
                response_time = time.time() - start_time
                success = resp.status == 200

                self.results.append(TestResult(
                    timestamp=start_time,
                    method='POST',
                    endpoint='/booking/confirm',
                    status_code=resp.status,
                    response_time=response_time,
                    success=success
                ))

                if success and booking_id in self.active_bookings:
                    self.active_bookings[booking_id]['status'] = 'confirmed'

                return success

        except Exception as e:
            response_time = time.time() - start_time
            self.results.append(TestResult(
                timestamp=start_time,
                method='POST',
                endpoint='/booking/confirm',
                status_code=0,
                response_time=response_time,
                success=False,
                error=str(e)
            ))

        return False

    async def cancel_booking(self, user: Dict[str, Any]) -> bool:
        """Cancel a random user booking"""
        user_bookings = [b for b in self.active_bookings.values()
                         if b['user_id'] == user['user_id'] and b['status'] in ['reserved', 'confirmed']]

        if not user_bookings:
            return False

        booking = random.choice(user_bookings)
        return await self.cancel_booking_by_id(user, booking['booking_id'])

    async def cancel_booking_by_id(self, user: Dict[str, Any], booking_id: str) -> bool:
        """Cancel specific booking"""
        start_time = time.time()
        try:
            async with self.session.delete(
                    f"{self.config.api_base_url}/booking/{booking_id}",
                    headers=user['headers']
            ) as resp:
                response_time = time.time() - start_time
                success = resp.status == 200

                self.results.append(TestResult(
                    timestamp=start_time,
                    method='DELETE',
                    endpoint=f'/booking/{booking_id}',
                    status_code=resp.status,
                    response_time=response_time,
                    success=success
                ))

                if success and booking_id in self.active_bookings:
                    self.active_bookings[booking_id]['status'] = 'cancelled'

                return success

        except Exception as e:
            response_time = time.time() - start_time
            self.results.append(TestResult(
                timestamp=start_time,
                method='DELETE',
                endpoint=f'/booking/{booking_id}',
                status_code=0,
                response_time=response_time,
                success=False,
                error=str(e)
            ))

        return False

    async def get_user_bookings(self, user: Dict[str, Any]):
        """Get user's bookings"""
        start_time = time.time()
        try:
            async with self.session.get(
                    f"{self.config.api_base_url}/user/bookings",
                    headers=user['headers']
            ) as resp:
                response_time = time.time() - start_time
                success = resp.status == 200

                self.results.append(TestResult(
                    timestamp=start_time,
                    method='GET',
                    endpoint='/user/bookings',
                    status_code=resp.status,
                    response_time=response_time,
                    success=success
                ))

        except Exception as e:
            response_time = time.time() - start_time
            self.results.append(TestResult(
                timestamp=start_time,
                method='GET',
                endpoint='/user/bookings',
                status_code=0,
                response_time=response_time,
                success=False,
                error=str(e)
            ))

    def analyze_results(self) -> Dict[str, Any]:
        """Analyze test results"""
        if not self.results:
            return {'error': 'No results to analyze'}

        total_requests = len(self.results)
        successful_requests = sum(1 for r in self.results if r.success)
        failed_requests = total_requests - successful_requests

        response_times = [r.response_time * 1000 for r in self.results]  # Convert to ms

        # Group by endpoint
        endpoint_stats = {}
        for result in self.results:
            key = f"{result.method} {result.endpoint}"
            if key not in endpoint_stats:
                endpoint_stats[key] = {'total': 0, 'success': 0, 'response_times': []}

            endpoint_stats[key]['total'] += 1
            if result.success:
                endpoint_stats[key]['success'] += 1
            endpoint_stats[key]['response_times'].append(result.response_time * 1000)

        # Calculate percentiles
        def percentile(data, p):
            return statistics.quantiles(sorted(data), n=100)[p - 1] if data else 0

        analysis = {
            'summary': {
                'total_requests': total_requests,
                'successful_requests': successful_requests,
                'failed_requests': failed_requests,
                'success_rate': (successful_requests / total_requests * 100) if total_requests > 0 else 0,
                'test_duration': self.config.test_duration_minutes,
                'concurrent_users': self.config.concurrent_users,
                'avg_rps': total_requests / (self.config.test_duration_minutes * 60)
            },
            'response_times': {
                'min': min(response_times) if response_times else 0,
                'max': max(response_times) if response_times else 0,
                'avg': statistics.mean(response_times) if response_times else 0,
                'median': statistics.median(response_times) if response_times else 0,
                'p95': percentile(response_times, 95) if response_times else 0,
                'p99': percentile(response_times, 99) if response_times else 0
            },
            'endpoints': {}
        }

        for endpoint, stats in endpoint_stats.items():
            times = stats['response_times']
            analysis['endpoints'][endpoint] = {
                'total_requests': stats['total'],
                'successful_requests': stats['success'],
                'success_rate': (stats['success'] / stats['total'] * 100) if stats['total'] > 0 else 0,
                'avg_response_time': statistics.mean(times) if times else 0,
                'p95_response_time': percentile(times, 95) if times else 0
            }

        return analysis

    async def cleanup(self):
        """Cleanup resources"""
        if self.session:
            await self.session.close()

    def save_results(self, filename: str):
        """Save results to file"""
        analysis = self.analyze_results()

        os.makedirs('results', exist_ok=True)

        with open(f'results/{filename}', 'w') as f:
            json.dump(analysis, f, indent=2)

        # Also save raw results
        raw_results = [
            {
                'timestamp': r.timestamp,
                'method': r.method,
                'endpoint': r.endpoint,
                'status_code': r.status_code,
                'response_time': r.response_time,
                'success': r.success,
                'error': r.error
            }
            for r in self.results
        ]

        with open(f'results/raw_{filename}', 'w') as f:
            json.dump(raw_results, f, indent=2)


def load_config(config_file: str) -> TestConfig:
    """Load configuration from YAML file"""
    with open(config_file, 'r') as f:
        config_data = yaml.safe_load(f)

    return TestConfig(
        api_base_url=os.environ.get('API_BASE_URL', config_data['api_base_url']),
        concurrent_users=config_data.get('concurrent_users', 10),
        test_duration_minutes=config_data.get('test_duration_minutes', 5),
        requests_per_second=config_data.get('requests_per_second', 10),
        scenario=os.environ.get('TEST_TYPE', config_data.get('scenario', 'mixed')),
        ramp_up_seconds=config_data.get('ramp_up_seconds', 60),
        ramp_down_seconds=config_data.get('ramp_down_seconds', 30)
    )


async def main():
    parser = argparse.ArgumentParser(description='Ticket Booking Load Generator')
    parser.add_argument('--config', default='config/test_config.yaml', help='Config file path')
    parser.add_argument('--output', default=None, help='Output file name')

    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)

    # Create load generator
    generator = TicketBookingLoadGenerator(config)

    try:
        # Setup and run test
        await generator.setup()
        await generator.run_test()

        # Analyze and save results
        analysis = generator.analyze_results()

        print("\n" + "=" * 50)
        print("LOAD TEST RESULTS")
        print("=" * 50)
        print(f"Total Requests: {analysis['summary']['total_requests']}")
        print(f"Success Rate: {analysis['summary']['success_rate']:.2f}%")
        print(f"Average RPS: {analysis['summary']['avg_rps']:.2f}")
        print(f"Average Response Time: {analysis['response_times']['avg']:.2f}ms")
        print(f"95th Percentile: {analysis['response_times']['p95']:.2f}ms")
        print(f"99th Percentile: {analysis['response_times']['p99']:.2f}ms")

        # Save results
        output_file = args.output or f"load_test_{config.scenario}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        generator.save_results(output_file)
        print(f"\nResults saved to: results/{output_file}")

    finally:
        await generator.cleanup()


if __name__ == "__main__":
    asyncio.run(main())