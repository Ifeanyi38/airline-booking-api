import os
import django
import time
import statistics
import csv
from datetime import datetime

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'airline_project.settings')
django.setup()

from booking.models import Flight, Passenger, Booking, Seat
from pymongo import MongoClient
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # prevents charts from opening as windows — just saves them
import numpy as np

# ── MongoDB connection ────────────────────────────────────────────────────────
client = MongoClient('mongodb://localhost:27017/')
db     = client['airline_booking']

# ── Measurement function ──────────────────────────────────────────────────────

def measure(func, runs=100):
    """Runs a function 100 times and returns min, max, avg and stdev in ms"""
    times = []
    for _ in range(runs):
        start = time.perf_counter()
        func()
        end   = time.perf_counter()
        times.append((end - start) * 1000)

    return {
        'min':   round(min(times), 3),
        'max':   round(max(times), 3),
        'avg':   round(sum(times) / len(times), 3),
        'stdev': round(statistics.stdev(times), 3)
    }


# ── MySQL operations ──────────────────────────────────────────────────────────

def mysql_search_flights():
    """Search flights by origin and destination city"""
    Flight.objects.filter(
        origin__city__icontains='London',
        destination__city__icontains='New York',
        status='scheduled'
    ).select_related('origin', 'destination').count()


def mysql_create_booking():
    """Read the first available passenger, flight and seat for timing only"""
    passenger = Passenger.objects.first()
    flight    = Flight.objects.filter(status='scheduled').first()
    seat      = Seat.objects.filter(aircraft=flight.aircraft).first()
    return passenger, flight, seat


def mysql_view_bookings():
    """Fetch all bookings for a passenger by email"""
    try:
        passenger = Passenger.objects.first()
        Booking.objects.filter(
            passenger=passenger
        ).select_related('flight', 'flight__origin', 'flight__destination', 'seat').count()
    except Exception:
        pass


def mysql_cancel_booking():
    """Measure update query performance — find a confirmed booking"""
    Booking.objects.filter(status='confirmed').first()


def mysql_seat_availability():
    """Check available seats for a flight"""
    flight = Flight.objects.first()
    booked_seat_ids = Booking.objects.filter(
        flight=flight,
        status='confirmed'
    ).values_list('seat_id', flat=True)
    Seat.objects.filter(
        aircraft=flight.aircraft
    ).exclude(id__in=booked_seat_ids).count()


# ── MongoDB operations ────────────────────────────────────────────────────────

def mongo_search_flights():
    """Search flights by origin and destination city"""
    list(db.flights.find({
        'origin.city':      {'$regex': 'London', '$options': 'i'},
        'destination.city': {'$regex': 'New York', '$options': 'i'},
        'status':           'scheduled'
    }))


def mongo_create_booking():
    """Read first passenger and flight for timing only"""
    db.passengers.find_one()
    db.flights.find_one({'status': 'scheduled'})


def mongo_view_bookings():
    """Fetch all bookings for a passenger by email"""
    passenger = db.passengers.find_one()
    if passenger:
        list(db.bookings.find({
            'passenger_id': passenger['_id']
        }))


def mongo_cancel_booking():
    """Measure update query performance — find a confirmed booking"""
    db.bookings.find_one({'status': 'confirmed'})


def mongo_seat_availability():
    """Check available seats for a flight"""
    flight = db.flights.find_one()
    if flight:
        booked = db.bookings.distinct(
            'seat.seat_number',
            {'flight_id': flight['_id'], 'status': 'confirmed'}
        )
        aircraft = db.aircraft.find_one({'_id': flight['aircraft_id']})
        if aircraft:
            available = [s for s in aircraft['seats']
                        if s['seat_number'] not in booked]


# ── Run all benchmarks ────────────────────────────────────────────────────────

def run_benchmarks():
    operations = [
        ('Search flights',        mysql_search_flights,    mongo_search_flights),
        ('View bookings',         mysql_view_bookings,     mongo_view_bookings),
        ('Cancel booking',        mysql_cancel_booking,    mongo_cancel_booking),
        ('Seat availability',     mysql_seat_availability, mongo_seat_availability),
        ('Create booking (read)', mysql_create_booking,    mongo_create_booking),
    ]

    results = []

    print(f"\n{'='*70}")
    print(f"BENCHMARK RESULTS — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}")
    print(f"{'Operation':<25} {'DB':<10} {'Avg (ms)':<12} {'Min (ms)':<12} {'Max (ms)':<12} {'StDev'}")
    print(f"{'-'*70}")

    for name, mysql_func, mongo_func in operations:
        mysql_result = measure(mysql_func)
        print(f"{name:<25} {'MySQL':<10} {mysql_result['avg']:<12} {mysql_result['min']:<12} {mysql_result['max']:<12} {mysql_result['stdev']}")

        mongo_result = measure(mongo_func)
        print(f"{'':25} {'MongoDB':<10} {mongo_result['avg']:<12} {mongo_result['min']:<12} {mongo_result['max']:<12} {mongo_result['stdev']}")
        print(f"{'-'*70}")

        results.append({
            'operation':   name,
            'mysql_avg':   mysql_result['avg'],
            'mysql_min':   mysql_result['min'],
            'mysql_max':   mysql_result['max'],
            'mysql_stdev': mysql_result['stdev'],
            'mongo_avg':   mongo_result['avg'],
            'mongo_min':   mongo_result['min'],
            'mongo_max':   mongo_result['max'],
            'mongo_stdev': mongo_result['stdev'],
        })

    return results


# ── Export to CSV ─────────────────────────────────────────────────────────────

def export_csv(results, filename='benchmark_results.csv'):
    with open(filename, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    print(f"\nResults exported to {filename}")


# ── Generate charts ───────────────────────────────────────────────────────────

def generate_charts(results):
    operations  = [r['operation']   for r in results]
    mysql_avgs  = [r['mysql_avg']   for r in results]
    mongo_avgs  = [r['mongo_avg']   for r in results]
    mysql_stdev = [r['mysql_stdev'] for r in results]
    mongo_stdev = [r['mongo_stdev'] for r in results]
    mysql_min   = [r['mysql_min']   for r in results]
    mongo_min   = [r['mongo_min']   for r in results]
    mysql_max   = [r['mysql_max']   for r in results]
    mongo_max   = [r['mongo_max']   for r in results]

    x     = np.arange(len(operations))
    width = 0.35

    # ── Chart 1: Average with error bars (stdev) ──────────────────────────
    fig, ax = plt.subplots(figsize=(13, 6))
    bars1 = ax.bar(x - width/2, mysql_avgs, width, label='MySQL',
                   color='#4a90d9', yerr=mysql_stdev, capsize=5)
    bars2 = ax.bar(x + width/2, mongo_avgs, width, label='MongoDB',
                   color='#e8c96e', yerr=mongo_stdev, capsize=5)
    ax.set_xlabel('Operation')
    ax.set_ylabel('Time (ms)')
    ax.set_title('MySQL vs MongoDB — Average Query Time with Standard Deviation')
    ax.set_xticks(x)
    ax.set_xticklabels(operations, rotation=15, ha='right')
    ax.legend()
    ax.bar_label(bars1, padding=8, fmt='%.2f')
    ax.bar_label(bars2, padding=8, fmt='%.2f')
    plt.tight_layout()
    plt.savefig('chart_avg_stdev.png', dpi=150)
    plt.close()
    print("Chart 1 saved — chart_avg_stdev.png")

    # ── Chart 2: Min, Avg, Max grouped per operation ──────────────────────
    fig, axes = plt.subplots(1, len(operations), figsize=(18, 6), sharey=False)
    fig.suptitle('MySQL vs MongoDB — Min, Avg, Max per Operation', fontsize=13)

    for i, (ax, op) in enumerate(zip(axes, operations)):
        metrics    = ['Min', 'Avg', 'Max']
        mysql_vals = [mysql_min[i], mysql_avgs[i], mysql_max[i]]
        mongo_vals = [mongo_min[i], mongo_avgs[i], mongo_max[i]]

        xi = np.arange(3)
        ax.bar(xi - 0.2, mysql_vals, 0.35, label='MySQL',   color='#4a90d9')
        ax.bar(xi + 0.2, mongo_vals, 0.35, label='MongoDB', color='#e8c96e')
        ax.set_title(op, fontsize=9)
        ax.set_xticks(xi)
        ax.set_xticklabels(metrics, fontsize=8)
        ax.set_ylabel('ms' if i == 0 else '')
        if i == 0:
            ax.legend(fontsize=8)

    plt.tight_layout()
    plt.savefig('chart_min_avg_max.png', dpi=150)
    plt.close()
    print("Chart 2 saved — chart_min_avg_max.png")

    # ── Chart 3: Standard deviation comparison ────────────────────────────
    fig, ax = plt.subplots(figsize=(13, 6))
    bars1 = ax.bar(x - width/2, mysql_stdev, width, label='MySQL',   color='#4a90d9')
    bars2 = ax.bar(x + width/2, mongo_stdev, width, label='MongoDB', color='#e8c96e')
    ax.set_xlabel('Operation')
    ax.set_ylabel('Standard Deviation (ms)')
    ax.set_title('MySQL vs MongoDB — Consistency (Lower = More Consistent)')
    ax.set_xticks(x)
    ax.set_xticklabels(operations, rotation=15, ha='right')
    ax.legend()
    ax.bar_label(bars1, padding=3, fmt='%.2f')
    ax.bar_label(bars2, padding=3, fmt='%.2f')
    plt.tight_layout()
    plt.savefig('chart_stdev.png', dpi=150)
    plt.close()
    print("Chart 3 saved — chart_stdev.png")

    # ── Chart 4: Max response time comparison ─────────────────────────────
    fig, ax = plt.subplots(figsize=(13, 6))
    bars1 = ax.bar(x - width/2, mysql_max, width, label='MySQL',   color='#4a90d9')
    bars2 = ax.bar(x + width/2, mongo_max, width, label='MongoDB', color='#e8c96e')
    ax.set_xlabel('Operation')
    ax.set_ylabel('Max Time (ms)')
    ax.set_title('MySQL vs MongoDB — Worst Case Response Time')
    ax.set_xticks(x)
    ax.set_xticklabels(operations, rotation=15, ha='right')
    ax.legend()
    ax.bar_label(bars1, padding=3, fmt='%.2f')
    ax.bar_label(bars2, padding=3, fmt='%.2f')
    plt.tight_layout()
    plt.savefig('chart_max.png', dpi=150)
    plt.close()
    print("Chart 4 saved — chart_max.png")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    results = run_benchmarks()
    export_csv(results)
    generate_charts(results)