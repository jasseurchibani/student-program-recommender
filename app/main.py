"""FastAPI application for program recommendation system."""

import csv
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .models import (
    UserProfile,
    RecommendationResponse,
    Recommendation,
    FeedbackRequest
)
from .recommender import engine
from .config import FEEDBACK_LOG, DEFAULT_K

# Initialize FastAPI app
app = FastAPI(
    title="Student Program Recommendation API",
    description="Hybrid recommendation system for suggesting study programs based on interests and grades",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for UI
ui_path = Path(__file__).parent.parent / "ui"
if ui_path.exists():
    app.mount("/ui", StaticFiles(directory=str(ui_path), html=True), name="ui")


@app.on_event("startup")
async def startup_event():
    """Load models on application startup."""
    try:
        engine.load_models()
        print("✓ Models loaded successfully")
    except Exception as e:
        print(f"✗ Error loading models: {e}")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "message": "Student Program Recommendation API",
        "status": "running",
        "version": "1.0.0"
    }


@app.post("/recommend", response_model=RecommendationResponse)
async def get_recommendations(
    profile: UserProfile,
    k: Optional[int] = DEFAULT_K,
    approach: Optional[str] = "hybrid"
):
    """
    Generate program recommendations based on user profile.
    
    Args:
        profile: User profile with interests and grades
        k: Number of recommendations to return (default: 5)
        approach: Recommendation approach - 'content-based', 'collaborative', or 'hybrid' (default)
    
    Returns:
        List of recommended programs with explanations
    """
    try:
        # Normalize approach coming from UI/query params
        approach = (approach or "hybrid").strip().lower()
        if approach in {"content", "content_based", "contentbased"}:
            approach = "content-based"
        if approach in {"cf", "collab", "collaborative-filtering", "collaborative_filtering"}:
            approach = "collaborative"
        if approach not in {"content-based", "collaborative", "hybrid"}:
            raise HTTPException(status_code=400, detail=f"Unknown approach '{approach}'.")

        # Ensure models are loaded
        if not engine.loaded:
            engine.load_models()
        
        print(f"[API] Received request with approach: {approach}")
        print(f"[API] User interests: {profile.interests[:100]}...")
        
        # Generate recommendations based on approach
        if approach == "content-based":
            print("[API] Routing to CONTENT-BASED recommendations")
            recs = engine.content_based_recommendations(profile.interests, k=k)
            recommendations = []
            for program_id, score, explanation in recs:
                program = engine.programs_df[engine.programs_df['program_id'] == program_id].iloc[0]
                recommendations.append(Recommendation(
                    program_id=program_id,
                    program_name=program['name'],
                    description=program['description'],
                    skills=program.get('tags_text', program.get('skills', '')),
                    score=score,
                    explanation=explanation
                ))
        
        elif approach == "collaborative":
            print("[API] Routing to COLLABORATIVE FILTERING recommendations")
            # For new users without user_id, simulate collaborative filtering
            if not profile.user_id:
                recs = engine.new_user_collaborative_recommendations(profile.interests, k=k)
                if not recs:
                    # Fallback to content-based if CF model not available
                    recs = engine.content_based_recommendations(profile.interests, k=k)
                    recommendations = []
                    for program_id, score, explanation in recs:
                        program = engine.programs_df[engine.programs_df['program_id'] == program_id].iloc[0]
                        recommendations.append(Recommendation(
                            program_id=program_id,
                            program_name=program['name'],
                            description=program['description'],
                            skills=program.get('tags_text', program.get('skills', '')),
                            score=score,
                            explanation=explanation
                        ))
                else:
                    recommendations = []
                    for program_id, score, explanation in recs:
                        program = engine.programs_df[engine.programs_df['program_id'] == program_id].iloc[0]
                        recommendations.append(Recommendation(
                            program_id=program_id,
                            program_name=program['name'],
                            description=program['description'],
                            skills=program.get('tags_text', program.get('skills', '')),
                            score=score,
                            explanation=explanation
                        ))
            else:
                recs = engine.collaborative_recommendations(profile.user_id, k=k)
                if not recs:
                    # User not in training data, use new user approach
                    recs = engine.new_user_collaborative_recommendations(profile.interests, k=k)
                    if not recs:
                        # Final fallback to content-based
                        recs = engine.content_based_recommendations(profile.interests, k=k)
                        recommendations = []
                        for program_id, score, explanation in recs:
                            program = engine.programs_df[engine.programs_df['program_id'] == program_id].iloc[0]
                            recommendations.append(Recommendation(
                                program_id=program_id,
                                program_name=program['name'],
                                description=program['description'],
                                skills=program.get('tags_text', program.get('skills', '')),
                                score=score,
                                explanation=explanation
                            ))
                    else:
                        recommendations = []
                        for program_id, score, explanation in recs:
                            program = engine.programs_df[engine.programs_df['program_id'] == program_id].iloc[0]
                            recommendations.append(Recommendation(
                                program_id=program_id,
                                program_name=program['name'],
                                description=program['description'],
                                skills=program.get('tags_text', program.get('skills', '')),
                                score=score,
                                explanation=explanation
                            ))
                else:
                    recommendations = []
                    for program_id, score, explanation in recs:
                        program = engine.programs_df[engine.programs_df['program_id'] == program_id].iloc[0]
                        recommendations.append(Recommendation(
                            program_id=program_id,
                            program_name=program['name'],
                            description=program['description'],
                            skills=program.get('tags_text', program.get('skills', '')),
                            score=score,
                            explanation=explanation
                        ))
        
        else:  # hybrid (default)
            print("[API] Routing to HYBRID recommendations")
            recs = engine.hybrid_recommendations(
                user_interests=profile.interests,
                user_id=profile.user_id,
                k=k
            )
            recommendations = [Recommendation(**rec) for rec in recs]
        
        return RecommendationResponse(
            user_id=profile.user_id,
            recommendations=recommendations,
            approach=approach
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating recommendations: {str(e)}")


@app.post("/feedback")
async def submit_feedback(feedback: FeedbackRequest):
    """
    Log user feedback on recommendations.
    
    Args:
        feedback: Feedback data including user_id, program_id, and feedback_type
    
    Returns:
        Confirmation message
    """
    try:
        # Ensure feedback log directory exists
        FEEDBACK_LOG.parent.mkdir(parents=True, exist_ok=True)
        
        # Check if file exists to determine if we need to write header
        file_exists = FEEDBACK_LOG.exists()
        
        # Append feedback to CSV
        with open(FEEDBACK_LOG, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write header if file is new
            if not file_exists:
                writer.writerow(['timestamp', 'user_id', 'program_id', 'feedback_type', 'session_id'])
            
            # Write feedback data
            writer.writerow([
                datetime.now().isoformat(),
                feedback.user_id or 'anonymous',
                feedback.program_id,
                feedback.feedback_type,
                feedback.session_id or ''
            ])
        
        return {
            "message": "Feedback recorded successfully",
            "feedback_type": feedback.feedback_type,
            "program_id": feedback.program_id
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error recording feedback: {str(e)}")


@app.get("/programs")
async def get_all_programs():
    """
    Get list of all available programs.
    
    Returns:
        List of all programs with their details
    """
    try:
        if not engine.loaded:
            engine.load_models()
        
        programs = engine.programs_df.to_dict('records')
        return {"programs": programs, "count": len(programs)}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching programs: {str(e)}")


@app.get("/health")
async def health_check():
    """
    Detailed health check with model status.
    
    Returns:
        System health information
    """
    return {
        "status": "healthy",
        "models_loaded": engine.loaded,
        "tfidf_available": engine.tfidf_vectorizer is not None,
        "cf_model_available": engine.cf_model is not None,
        "programs_loaded": engine.programs_df is not None if engine.loaded else False
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
