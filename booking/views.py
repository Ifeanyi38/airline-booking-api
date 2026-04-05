from django.shortcuts import render

# Create your views here.
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Airport, Aircraft, Flight, Seat, Passenger, Booking
from .serializers import FlightSerializer, BookingSerializer, PassengerSerializer, SeatSerializer
import random
import string


def generate_booking_ref():
    # Generates a unique booking reference e.g. SK4J9XQ2
    return 'SK' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))


# ── FLIGHTS ──────────────────────────────────────────────────────────────────

@api_view(['GET'])
def search_flights(request):
    # Get search parameters from URL query string
    from_city = request.GET.get('from', '')
    to_city   = request.GET.get('to', '')

    flights = Flight.objects.filter(
        origin__city__icontains=from_city,
        destination__city__icontains=to_city,
        status='scheduled'
    ).select_related('origin', 'destination', 'aircraft')

    serializer = FlightSerializer(flights, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def get_flight_seats(request, flight_id):
    try:
        flight = Flight.objects.get(id=flight_id)
    except Flight.DoesNotExist:
        return Response({'error': 'Flight not found'}, status=status.HTTP_404_NOT_FOUND)

    # Get all seats for this flight's aircraft
    all_seats = Seat.objects.filter(aircraft=flight.aircraft)

    # Get already booked seat ids for this flight
    booked_seat_ids = Booking.objects.filter(
        flight=flight,
        status='confirmed'
    ).values_list('seat_id', flat=True)

    # Mark each seat as available or taken
    seats_data = []
    for seat in all_seats:
        seats_data.append({
            'id':          seat.id,
            'seat_number': seat.seat_number,
            'seat_class':  seat.seat_class,
            'available':   seat.id not in booked_seat_ids
        })

    return Response(seats_data)


# ── BOOKINGS ─────────────────────────────────────────────────────────────────

@api_view(['POST'])
def create_booking(request):
    data = request.data

    # Get or create passenger by email
    passenger, created = Passenger.objects.get_or_create(
        email=data['email'],
        defaults={
            'first_name':      data['first_name'],
            'last_name':       data['last_name'],
            'phone':           data.get('phone', ''),
            'passport_number': data['passport_number'],
            'date_of_birth':   data['date_of_birth'],
        }
    )

    # Get flight and seat
    try:
        flight = Flight.objects.get(id=data['flight_id'])
        seat   = Seat.objects.get(id=data['seat_id'])
    except (Flight.DoesNotExist, Seat.DoesNotExist):
        return Response({'error': 'Flight or seat not found'}, status=status.HTTP_404_NOT_FOUND)

    # Check seat is not already booked
    if Booking.objects.filter(flight=flight, seat=seat, status='confirmed').exists():
        return Response({'error': 'Seat already booked'}, status=status.HTTP_400_BAD_REQUEST)

    # Create the booking
    booking = Booking.objects.create(
        passenger         = passenger,
        flight            = flight,
        seat              = seat,
        booking_reference = generate_booking_ref(),
        status            = 'confirmed',
        total_price       = flight.base_price,
    )

    serializer = BookingSerializer(booking)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
def get_bookings_by_email(request):
    # Get all bookings for a passenger by email
    email = request.GET.get('email', '')

    try:
        passenger = Passenger.objects.get(email=email)
    except Passenger.DoesNotExist:
        return Response([], status=status.HTTP_200_OK)

    bookings = Booking.objects.filter(
        passenger=passenger
    ).select_related('flight', 'flight__origin', 'flight__destination', 'seat')

    serializer = BookingSerializer(bookings, many=True)
    return Response(serializer.data)


@api_view(['PATCH'])
def cancel_booking(request, booking_id):
    try:
        booking = Booking.objects.get(id=booking_id)
    except Booking.DoesNotExist:
        return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)

    # Only confirmed bookings can be cancelled
    if booking.status != 'confirmed':
        return Response({'error': 'Booking is not confirmed'}, status=status.HTTP_400_BAD_REQUEST)

    booking.status = 'cancelled'
    booking.save()

    serializer = BookingSerializer(booking)
    return Response(serializer.data)