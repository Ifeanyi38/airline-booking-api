from django.db import models


class Airport(models.Model):
    code    = models.CharField(max_length=3, unique=True)
    name    = models.CharField(max_length=100)
    city    = models.CharField(max_length=100)
    country = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.code} — {self.city}"


class Aircraft(models.Model):
    model       = models.CharField(max_length=100)
    total_seats = models.PositiveIntegerField()

    def __str__(self):
        return self.model


class Flight(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('delayed',   'Delayed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    ]

    flight_number  = models.CharField(max_length=10, unique=True)
    aircraft       = models.ForeignKey(Aircraft, on_delete=models.PROTECT,
                                       related_name='flights')
    origin         = models.ForeignKey(Airport, on_delete=models.PROTECT,
                                       related_name='departures')
    destination    = models.ForeignKey(Airport, on_delete=models.PROTECT,
                                       related_name='arrivals')
    departure_time = models.DateTimeField()
    arrival_time   = models.DateTimeField()
    base_price     = models.DecimalField(max_digits=10, decimal_places=2)
    status         = models.CharField(max_length=20, choices=STATUS_CHOICES,
                                      default='scheduled')

    def __str__(self):
        return f"{self.flight_number}: {self.origin.code} → {self.destination.code}"


class Seat(models.Model):
    CLASS_CHOICES = [
        ('economy',  'Economy'),
        ('business', 'Business'),
        ('first',    'First'),
    ]

    aircraft     = models.ForeignKey(Aircraft, on_delete=models.CASCADE,
                                     related_name='seats')
    seat_number  = models.CharField(max_length=4)
    seat_class   = models.CharField(max_length=10, choices=CLASS_CHOICES)

    class Meta:
        unique_together = ('aircraft', 'seat_number')

    def __str__(self):
        return f"{self.seat_number} ({self.seat_class})"


class Passenger(models.Model):
    first_name      = models.CharField(max_length=50)
    last_name       = models.CharField(max_length=50)
    email           = models.EmailField(unique=True)
    phone           = models.CharField(max_length=20, blank=True)
    passport_number = models.CharField(max_length=20, unique=True)
    date_of_birth   = models.DateField()

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Booking(models.Model):
    STATUS_CHOICES = [
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('pending',   'Pending'),
    ]

    passenger         = models.ForeignKey(Passenger, on_delete=models.PROTECT,
                                          related_name='bookings')
    flight            = models.ForeignKey(Flight, on_delete=models.PROTECT,
                                          related_name='bookings')
    seat              = models.ForeignKey(Seat, on_delete=models.PROTECT,
                                          related_name='bookings')
    booking_reference = models.CharField(max_length=10, unique=True)
    status            = models.CharField(max_length=20, choices=STATUS_CHOICES,
                                         default='confirmed')
    total_price       = models.DecimalField(max_digits=10, decimal_places=2)
    booked_at         = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Prevents two passengers booking the same seat on the same flight
        unique_together = ('flight', 'seat')

    def __str__(self):
        return f"{self.booking_reference} — {self.passenger}"