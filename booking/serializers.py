from rest_framework import serializers
from .models import Airport, Aircraft, Flight, Seat, Passenger, Booking


class AirportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Airport
        fields = '__all__'


class AircraftSerializer(serializers.ModelSerializer):
    class Meta:
        model = Aircraft
        fields = '__all__'


class SeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seat
        fields = '__all__'


class FlightSerializer(serializers.ModelSerializer):
    # Returns full airport details instead of just the id
    origin      = AirportSerializer(read_only=True)
    destination = AirportSerializer(read_only=True)

    class Meta:
        model = Flight
        fields = '__all__'


class PassengerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Passenger
        fields = '__all__'


class BookingSerializer(serializers.ModelSerializer):
    # Returns full details instead of just ids
    passenger = PassengerSerializer(read_only=True)
    flight    = FlightSerializer(read_only=True)
    seat      = SeatSerializer(read_only=True)

    class Meta:
        model = Booking
        fields = '__all__'