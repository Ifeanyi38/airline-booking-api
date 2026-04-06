import os
import sys
import django
import random
import string
from datetime import timedelta
from decimal import Decimal

# Set up Django environment so we can use the ORM
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'airline_project.settings')
django.setup()

from faker import Faker
from booking.models import Airport, Aircraft, Flight, Seat, Passenger, Booking
from pymongo import MongoClient
from bson import ObjectId, Decimal128
from datetime import datetime

fake = Faker()
Faker.seed(42)
random.seed(42)

# ── Config ───────────────────────────────────────────────────────────────────
# Change these numbers when you want to scale up for load testing
NUM_PASSENGERS = 200
NUM_FLIGHTS    = 100
NUM_BOOKINGS   = 500

AIRPORTS = [
    ("LHR", "Heathrow",          "London",      "UK"),
    ("JFK", "John F. Kennedy",   "New York",    "USA"),
    ("DXB", "Dubai Intl",        "Dubai",       "UAE"),
    ("CDG", "Charles de Gaulle", "Paris",       "France"),
    ("SIN", "Changi",            "Singapore",   "Singapore"),
    ("NRT", "Narita",            "Tokyo",       "Japan"),
    ("LAX", "Los Angeles Intl",  "Los Angeles", "USA"),
    ("SYD", "Kingsford Smith",   "Sydney",      "Australia"),
    ("CPT", "Cape Town Intl",    "Cape Town",   "South Africa"),
    ("ABV", "Nnamdi Azikiwe",    "Abuja",       "Nigeria"),
]

AIRCRAFT_MODELS = [
    ("Boeing 737",   180),
    ("Airbus A320",  150),
    ("Boeing 777",   350),
    ("Airbus A380",  555),
    ("Boeing 787",   290),
]


def random_booking_ref():
    return 'SK' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))


def generate_seats(aircraft, total_seats):
    rows = total_seats // 6
    for row in range(1, rows + 1):
        for col in ['A', 'B', 'C', 'D', 'E', 'F']:
            if row <= 2:
                seat_class = 'first'
            elif row <= int(rows * 0.2):
                seat_class = 'business'
            else:
                seat_class = 'economy'
            Seat.objects.get_or_create(
                aircraft=aircraft,
                seat_number=f"{row}{col}",
                defaults={'seat_class': seat_class}
            )


# ── Seed MySQL via Django ORM ─────────────────────────────────────────────────

def seed_mysql():
    print("Seeding MySQL...")

    # Airports
    airport_objs = []
    for code, name, city, country in AIRPORTS:
        obj, _ = Airport.objects.get_or_create(
            code=code,
            defaults={'name': name, 'city': city, 'country': country}
        )
        airport_objs.append(obj)
    print(f"  {len(airport_objs)} airports created")

    # Aircraft and seats
    aircraft_objs = []
    for model, total in AIRCRAFT_MODELS:
        ac, created = Aircraft.objects.get_or_create(
            model=model,
            defaults={'total_seats': total}
        )
        aircraft_objs.append(ac)
        if created:
            generate_seats(ac, total)
    print(f"  {len(aircraft_objs)} aircraft created")

    # Passengers
    passengers = []
    for _ in range(NUM_PASSENGERS):
        try:
            p = Passenger.objects.create(
                first_name      = fake.first_name(),
                last_name       = fake.last_name(),
                email           = fake.unique.email(),
                phone           = fake.phone_number()[:20],
                passport_number = fake.unique.bothify('??#######'),
                date_of_birth   = fake.date_of_birth(minimum_age=18, maximum_age=80),
            )
            passengers.append(p)
        except Exception:
            pass
    print(f"  {len(passengers)} passengers created")

    # Flights
    flights = []
    used_numbers = set()
    for _ in range(NUM_FLIGHTS):
        origin, destination = random.sample(airport_objs, 2)
        aircraft = random.choice(aircraft_objs)
        departure = fake.date_time_between(start_date='+1d', end_date='+180d')
        duration  = timedelta(hours=random.randint(1, 14))

        fn = f"SK{random.randint(100, 999)}"
        while fn in used_numbers:
            fn = f"SK{random.randint(100, 999)}"
        used_numbers.add(fn)

        f = Flight.objects.create(
            flight_number  = fn,
            aircraft       = aircraft,
            origin         = origin,
            destination    = destination,
            departure_time = departure,
            arrival_time   = departure + duration,
            base_price     = Decimal(str(round(random.uniform(49, 1200), 2))),
            status         = 'scheduled',
        )
        flights.append(f)
    print(f"  {len(flights)} flights created")

    # Bookings
    booked = 0
    used_refs  = set()
    used_seats = set()

    for _ in range(NUM_BOOKINGS):
        flight    = random.choice(flights)
        passenger = random.choice(passengers)
        seats     = list(Seat.objects.filter(aircraft=flight.aircraft))
        available = [s for s in seats if (flight.id, s.id) not in used_seats]
        if not available:
            continue

        seat = random.choice(available)
        ref  = random_booking_ref()
        while ref in used_refs:
            ref = random_booking_ref()

        used_refs.add(ref)
        used_seats.add((flight.id, seat.id))

        Booking.objects.create(
            passenger         = passenger,
            flight            = flight,
            seat              = seat,
            booking_reference = ref,
            status            = random.choice(['confirmed', 'confirmed', 'confirmed', 'cancelled']),
            total_price       = flight.base_price,
        )
        booked += 1

    print(f"  {booked} bookings created")
    print("MySQL seeding complete!\n")


# ── Seed MongoDB via PyMongo ──────────────────────────────────────────────────

def seed_mongo():
    print("Seeding MongoDB...")

    client = MongoClient('mongodb://localhost:27017/')
    db     = client['airline_booking']

    # Drop existing collections
    db.airports.drop()
    db.aircraft.drop()
    db.flights.drop()
    db.passengers.drop()
    db.bookings.drop()

    # Airports
    airport_docs = []
    for code, name, city, country in AIRPORTS:
        doc = {"_id": ObjectId(), "code": code, "name": name,
               "city": city, "country": country}
        airport_docs.append(doc)
    db.airports.insert_many(airport_docs)
    print(f"  {len(airport_docs)} airports created")

    # Aircraft with embedded seats
    aircraft_docs = []
    for model, total in AIRCRAFT_MODELS:
        rows = total // 6
        seats = []
        for row in range(1, rows + 1):
            for col in ['A', 'B', 'C', 'D', 'E', 'F']:
                if row <= 2:
                    seat_class = 'first'
                elif row <= int(rows * 0.2):
                    seat_class = 'business'
                else:
                    seat_class = 'economy'
                seats.append({'seat_number': f"{row}{col}", 'seat_class': seat_class})

        doc = {"_id": ObjectId(), "model": model, "total_seats": total, "seats": seats}
        aircraft_docs.append(doc)
    db.aircraft.insert_many(aircraft_docs)
    print(f"  {len(aircraft_docs)} aircraft created")

    # Flights with embedded airport snapshots
    flight_docs = []
    used_numbers = set()
    for _ in range(NUM_FLIGHTS):
        origin      = random.choice(airport_docs)
        destination = random.choice([a for a in airport_docs if a != origin])
        aircraft    = random.choice(aircraft_docs)
        departure   = fake.date_time_between(start_date='+1d', end_date='+180d')
        duration    = timedelta(hours=random.randint(1, 14))

        fn = f"SK{random.randint(100, 999)}"
        while fn in used_numbers:
            fn = f"SK{random.randint(100, 999)}"
        used_numbers.add(fn)

        doc = {
            "_id":            ObjectId(),
            "flight_number":  fn,
            "aircraft_id":    aircraft["_id"],
            "origin":         {"code": origin["code"], "city": origin["city"], "country": origin["country"]},
            "destination":    {"code": destination["code"], "city": destination["city"], "country": destination["country"]},
            "departure_time": departure,
            "arrival_time":   departure + duration,
            "base_price":     Decimal128(str(round(random.uniform(49, 1200), 2))),
            "status":         "scheduled",
        }
        flight_docs.append(doc)
    db.flights.insert_many(flight_docs)
    print(f"  {len(flight_docs)} flights created")

    # Passengers
    passenger_docs = []
    for _ in range(NUM_PASSENGERS):
        doc = {
            "_id":             ObjectId(),
            "first_name":      fake.first_name(),
            "last_name":       fake.last_name(),
            "email":           fake.unique.email(),
            "phone":           fake.phone_number()[:20],
            "passport_number": fake.unique.bothify('??#######'),
            "date_of_birth":   datetime.combine(
                fake.date_of_birth(minimum_age=18, maximum_age=80),
                datetime.min.time()
            ),
        }
        passenger_docs.append(doc)
    db.passengers.insert_many(passenger_docs)
    print(f"  {len(passenger_docs)} passengers created")

    # Bookings with embedded snapshots
    booking_docs = []
    used_refs  = set()
    used_seats = set()

    for _ in range(NUM_BOOKINGS):
        flight    = random.choice(flight_docs)
        passenger = random.choice(passenger_docs)
        aircraft  = next(a for a in aircraft_docs if a["_id"] == flight["aircraft_id"])
        available = [s for s in aircraft["seats"]
                     if (str(flight["_id"]), s["seat_number"]) not in used_seats]
        if not available:
            continue

        seat = random.choice(available)
        ref  = random_booking_ref()
        while ref in used_refs:
            ref = random_booking_ref()

        used_refs.add(ref)
        used_seats.add((str(flight["_id"]), seat["seat_number"]))

        doc = {
            "_id":               ObjectId(),
            "passenger_id":      passenger["_id"],
            "flight_id":         flight["_id"],
            "booking_reference": ref,
            "status":            random.choice(['confirmed', 'confirmed', 'confirmed', 'cancelled']),
            "total_price":       flight["base_price"],
            "booked_at":         datetime.utcnow(),
            "seat": {
                "seat_number": seat["seat_number"],
                "seat_class":  seat["seat_class"],
            },
            "passenger_snapshot": {
                "first_name":      passenger["first_name"],
                "last_name":       passenger["last_name"],
                "email":           passenger["email"],
                "passport_number": passenger["passport_number"],
            },
            "flight_snapshot": {
                "flight_number":  flight["flight_number"],
                "origin":         flight["origin"]["code"],
                "destination":    flight["destination"]["code"],
                "departure_time": flight["departure_time"],
            },
        }
        booking_docs.append(doc)

    db.bookings.insert_many(booking_docs)
    print(f"  {len(booking_docs)} bookings created")
    print("MongoDB seeding complete!")


# ── Run both ──────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    seed_mysql()
    seed_mongo()