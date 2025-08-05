from flask import Blueprint, request, jsonify, g
from ..auth.utils import token_required
from ..models import db, Review, Ride, Profile
from datetime import datetime

review_bp = Blueprint("review", __name__, url_prefix="/reviews")

@review_bp.route("/", methods=["POST"])
@token_required
def create_review():
    data = request.get_json()
    reviewer = g.current_user

    required_fields = ["reviewee_id", "ride_id", "rating", "role"]
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    review = Review(
        reviewer_id=reviewer.id,
        reviewee_id=data["reviewee_id"],
        ride_id=data["ride_id"],
        rating=data["rating"],
        comment=data.get("comment"),
        role=data["role"].lower(),  # "driver" or "rider"
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    db.session.add(review)
    db.session.commit()

    return jsonify({"message": "Review created successfully", "review_id": review.id}), 201

@review_bp.route("/<review_id>", methods=["PATCH"])
@token_required
def update_review(review_id):
    data = request.get_json()
    reviewer = g.current_user

    review = Review.query.get(review_id)

    if not review:
        return jsonify({"error": "Review not found"}), 404
    if review.reviewer_id != reviewer.id:
        return jsonify({"error": "Reviews can only be updated by their writers."}), 403

    if "rating" in data:
        review.rating = data["rating"]
    if "comment" in data:
        review.comment = data["comment"]
    review.updated_at = datetime.utcnow()

    db.session.commit()

    return jsonify({"message": "Review updated successfully"})

@review_bp.route("/<review_id>", methods=["DELETE"])
@token_required
def delete_review(review_id):
    reviewer = g.current_user

    review = Review.query.get(review_id)

    if not review:
        return jsonify({"error": "Review not found"}), 404
    if review.reviewer_id != reviewer.id:
        return jsonify({"error": "Unauthorized"}), 403

    db.session.delete(review)
    db.session.commit()

    return jsonify({"message": "Review deleted successfully"})

@review_bp.route("/<profile_id>", methods=["GET"])
@token_required
def get_reviews(profile_id):
    role_filter = request.args.get("role")  # Optional: 'driver' or 'rider'

    # Validate profile exists
    profile = Profile.query.get(profile_id)
    if not profile:
        return jsonify({"error": "Profile not found"}), 404

    # Filter reviews received by this profile
    query = Review.query.filter_by(reviewee_id=profile_id)
    if role_filter in ("driver", "rider"):
        query = query.filter_by(role=role_filter)

    reviews = query.order_by(Review.created_at.desc()).all()

    return jsonify([
        {
            "id": r.id,
            "reviewer_id": r.reviewer_id,
            "reviewer_name": r.reviewer.name if r.reviewer else None,
            "ride_id": r.ride_id,
            "rating": r.rating,
            "comment": r.comment,
            "role": r.role,
            "created_at": r.created_at.isoformat()
        }
        for r in reviews
    ])

