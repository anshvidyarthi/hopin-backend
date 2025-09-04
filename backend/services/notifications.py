from backend.socket_handlers import send_notification_to_user
from backend.models import Profile, Ride, RideRequest, Message

class NotificationService:
    """Service class for sending different types of notifications"""
    
    @staticmethod
    def ride_request_received(driver_id: str, request: RideRequest, rider: Profile):
        """Notify driver of new ride request"""
        return send_notification_to_user(
            user_id=driver_id,
            notification_type="ride_request_received",
            title="New Ride Request",
            body=f"{rider.name} wants to join your ride",
            ride_id=request.ride_id,
            request_id=request.id,
            other_user_id=rider.id,
            action_data={
                "screen": "RideDetails",
                "params": {
                    "rideId": request.ride_id,
                    "mode": "driver"
                }
            }
        )
    
    @staticmethod
    def ride_request_accepted(rider_id: str, request: RideRequest, driver: Profile, ride: Ride):
        """Notify rider their request was accepted"""
        return send_notification_to_user(
            user_id=rider_id,
            notification_type="ride_request_accepted",
            title="Request Accepted!",
            body=f"{driver.name} accepted your ride request",
            ride_id=request.ride_id,
            request_id=request.id,
            other_user_id=driver.id,
            action_data={
                "screen": "Chat",
                "params": {
                    "conversation": {
                        "otherUser": {"id": driver.id, "name": driver.name},
                        "ride": {"id": ride.id},
                        "userRole": "rider"
                    }
                }
            }
        )
    
    @staticmethod
    def ride_request_declined(rider_id: str, request: RideRequest, driver: Profile):
        """Notify rider their request was declined"""
        return send_notification_to_user(
            user_id=rider_id,
            notification_type="ride_request_declined",
            title="Request Declined",
            body=f"{driver.name} declined your ride request",
            ride_id=request.ride_id,
            request_id=request.id,
            other_user_id=driver.id,
            action_data={
                "screen": "FindRide",
                "params": {}
            }
        )
    
    @staticmethod
    def new_message(receiver_id: str, message: Message, sender: Profile):
        """Notify user of new message"""
        return send_notification_to_user(
            user_id=receiver_id,
            notification_type="new_message",
            title=f"Message from {sender.name}",
            body=message.content[:50] + ("..." if len(message.content) > 50 else ""),
            message_id=message.id,
            ride_id=message.ride_id,
            other_user_id=sender.id,
            action_data={
                "screen": "Chat",
                "params": {
                    "conversation": {
                        "otherUser": {"id": sender.id, "name": sender.name},
                        "ride": {"id": message.ride_id}
                    }
                }
            }
        )
    
    @staticmethod
    def ride_cancelled(user_id: str, ride: Ride, cancelled_by: Profile):
        """Notify participants when ride is cancelled"""
        return send_notification_to_user(
            user_id=user_id,
            notification_type="ride_cancelled",
            title="Ride Cancelled",
            body=f"Ride from {ride.start_location} to {ride.end_location} was cancelled by {cancelled_by.name}",
            ride_id=ride.id,
            other_user_id=cancelled_by.id,
            action_data={
                "screen": "FindRide",
                "params": {}
            }
        )
    
    @staticmethod
    def ride_starting_soon(user_id: str, ride: Ride, other_user: Profile, user_role: str):
        """Remind users ride is starting in 30 minutes"""
        return send_notification_to_user(
            user_id=user_id,
            notification_type="ride_starting_soon",
            title="Ride Starting Soon",
            body=f"Your ride with {other_user.name} starts in 30 minutes",
            ride_id=ride.id,
            other_user_id=other_user.id,
            action_data={
                "screen": "RideDetails",
                "params": {
                    "rideId": ride.id,
                    "mode": user_role
                }
            }
        )
    
    @staticmethod
    def driver_arriving(rider_id: str, ride: Ride, driver: Profile):
        """Notify rider that driver is approaching"""
        return send_notification_to_user(
            user_id=rider_id,
            notification_type="driver_arriving",
            title="Driver Approaching",
            body=f"{driver.name} is approaching your pickup location",
            ride_id=ride.id,
            other_user_id=driver.id,
            action_data={
                "screen": "RideDetails",
                "params": {
                    "rideId": ride.id,
                    "mode": "rider"
                }
            }
        )
    
    @staticmethod
    def license_verification_complete(user_id: str, status: str):
        """Notify driver of license verification result"""
        title = "License Verified" if status == "VERIFIED" else "License Verification Failed"
        body = "You can now offer rides" if status == "VERIFIED" else "Please upload a valid license"
        
        return send_notification_to_user(
            user_id=user_id,
            notification_type="license_verification_complete",
            title=title,
            body=body,
            action_data={
                "screen": "Profile" if status == "VERIFIED" else "DriverVerificationUpload",
                "params": {}
            }
        )