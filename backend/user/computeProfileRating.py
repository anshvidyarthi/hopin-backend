def compute_average_rating(profile_id: str, role: str = "driver") -> float:
    from ..models import Review
    reviews = Review.query.filter_by(reviewee_id=profile_id, role=role).all()
    if not reviews:
        return 0.0
    return round(sum(r.rating for r in reviews) / len(reviews), 2)