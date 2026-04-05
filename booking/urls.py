from django.urls import path
from . import views

urlpatterns = [
    # Flight endpoints
    path('flights/', views.search_flights, name='search_flights'),
    path('flights/<int:flight_id>/seats/', views.get_flight_seats, name='get_flight_seats'),

    # Booking endpoints
    path('bookings/', views.get_bookings_by_email, name='get_bookings'),
    path('bookings/create/', views.create_booking, name='create_booking'),
    path('bookings/<int:booking_id>/cancel/', views.cancel_booking, name='cancel_booking'),
]