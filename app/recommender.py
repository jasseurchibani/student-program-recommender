"""Recommendation engine logic."""

try:
    import joblib  # type: ignore
except ImportError:  # pragma: no cover
    joblib = None
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict, Tuple
from pathlib import Path

from .config import (
    TFIDF_ARTIFACTS,
    COURSES_FILE_PROCESSED,
    CF_MODEL,
    PROGRAMS_FILE,
    TFIDF_VECTORIZER,
    TFIDF_MATRIX,
    HYBRID_CONTENT_WEIGHT,
    HYBRID_CF_WEIGHT,
)


class RecommendationEngine:
    """Hybrid recommendation engine combining content-based and collaborative filtering."""
    
    def __init__(self):
        """Load pre-trained models and data."""
        self.tfidf_vectorizer = None
        self.tfidf_matrix = None
        self.cf_model = None
        self.programs_df = None
        self.loaded = False
        
    def load_models(self):
        """Load all required models and data files."""
        if self.loaded:
            return

        if joblib is None:
            raise RuntimeError(
                "Missing dependency 'joblib'. Install it (pip install joblib) to load .joblib model artifacts."
            )
            
        try:
            # Prefer the exported notebook artifacts (vectorizer + course TF-IDF + catalog)
            if TFIDF_ARTIFACTS.exists():
                bundle = joblib.load(TFIDF_ARTIFACTS)
                self.tfidf_vectorizer = bundle.get("vectorizer")
                self.tfidf_matrix = bundle.get("X")

                # Prefer full course catalog if available (for descriptions), but keep
                # ordering aligned to the saved catalog in the artifacts.
                catalog = bundle.get("catalog")
                if COURSES_FILE_PROCESSED.exists():
                    full = pd.read_csv(COURSES_FILE_PROCESSED)
                    if catalog is not None and "course_id" in catalog.columns and "course_id" in full.columns:
                        full_by_id = full.set_index("course_id", drop=False)
                        aligned = (
                            catalog[["course_id"]]
                            .astype({"course_id": int})
                            .merge(
                                full_by_id,
                                left_on="course_id",
                                right_index=True,
                                how="left",
                                suffixes=("", "_full"),
                            )
                        )
                        courses_df = aligned
                    else:
                        courses_df = full
                elif catalog is not None:
                    courses_df = catalog
                else:
                    courses_df = None

                if courses_df is not None:
                    # Normalize into the existing "programs_df" contract expected by main.py
                    dfp = pd.DataFrame()
                    dfp["program_id"] = courses_df["course_id"].astype(str)
                    dfp["name"] = courses_df.get("Course Name", "").fillna("")
                    dfp["description"] = courses_df.get("Course Description", "").fillna("")
                    dfp["tags_text"] = courses_df.get("skills_cleaned", "").fillna("")
                    # Keep a few optional extras (UI can ignore them)
                    for col_in, col_out in [
                        ("Course URL", "url"),
                        ("University", "university"),
                        ("Difficulty Level", "difficulty"),
                        ("Course Rating", "rating"),
                    ]:
                        if col_in in courses_df.columns:
                            dfp[col_out] = courses_df[col_in]
                    self.programs_df = dfp

                    # Create combined text field like in the notebook
                    self.programs_df["text"] = (
                        self.programs_df["name"].astype(str)
                        + " "
                        + self.programs_df["description"].astype(str)
                        + " "
                        + self.programs_df["tags_text"].astype(str)
                    ).str.lower()
            else:
                # Fallback to legacy separate TF-IDF files if present
                if TFIDF_VECTORIZER.exists():
                    self.tfidf_vectorizer = joblib.load(TFIDF_VECTORIZER)
                if TFIDF_MATRIX.exists():
                    self.tfidf_matrix = joblib.load(TFIDF_MATRIX)
            
            # Load CF model
            if CF_MODEL.exists():
                self.cf_model = joblib.load(CF_MODEL)
            
            # Load program data
            if self.programs_df is None and PROGRAMS_FILE.exists():
                self.programs_df = pd.read_csv(PROGRAMS_FILE)
                # Create combined text field like in the training notebook
                self.programs_df['text'] = (self.programs_df['description'] + ' ' + 
                                           self.programs_df['tags_text']).str.lower()
            
            self.loaded = True
            print("✓ Models loaded successfully")
        except Exception as e:
            print(f"✗ Error loading models: {e}")
            raise

    @staticmethod
    def _normalize_scores_0_1(scores: List[float]) -> List[float]:
        if not scores:
            return scores
        mn = float(min(scores))
        mx = float(max(scores))
        if mx == mn:
            return [1.0 for _ in scores]
        return [(float(s) - mn) / (mx - mn) for s in scores]

    @staticmethod
    def _parse_interests_tokens(user_interests: str) -> List[str]:
        text = str(user_interests).lower().replace(",", " ")
        return [tok.strip() for tok in text.split() if tok.strip()]
        
    def content_based_recommendations(
        self, 
        user_interests: str, 
        k: int = 5
    ) -> List[Tuple[str, float, str]]:
        """Generate content-based recommendations using TF-IDF similarity."""
        print("[RECOMMENDER] Using CONTENT-BASED model")
        if not self.loaded:
            self.load_models()

        if self.tfidf_vectorizer is None or self.tfidf_matrix is None or self.programs_df is None:
            raise RuntimeError(
                "Content-based assets not loaded. Ensure models/content_based/tfidf_artifacts.joblib exists."
            )
        
        # Transform user interests to TF-IDF vector
        # UI sends comma-separated interests; the model was trained on free text, so
        # treating commas as spaces tends to work better.
        raw_interests = str(user_interests)
        model_interests = raw_interests.replace(",", " ")
        user_vector = self.tfidf_vectorizer.transform([model_interests])
        
        # Calculate cosine similarity with all programs
        similarities = cosine_similarity(user_vector, self.tfidf_matrix).flatten()
        
        # Get top-k programs with non-zero similarity
        # Sort by score descending
        scored_programs = [(idx, similarities[idx]) for idx in range(len(similarities))]
        scored_programs.sort(key=lambda x: x[1], reverse=True)
        
        # Filter to only meaningful matches (score > 0)
        relevant_programs = [(idx, score) for idx, score in scored_programs if score > 0]
        
        # Take top-k from relevant programs
        top_programs = relevant_programs[:k] if len(relevant_programs) >= k else relevant_programs
        
        recommendations = []
        for idx, score in top_programs:
            program = self.programs_df.iloc[idx]
            explanation = self._generate_content_explanation(raw_interests, program)
            recommendations.append((str(program['program_id']), float(score), explanation))
        
        return recommendations
    
    def collaborative_recommendations(
        self, 
        user_id: str, 
        k: int = 5
    ) -> List[Tuple[str, float, str]]:
        """Generate collaborative filtering recommendations."""
        print(f"[RECOMMENDER] Using COLLABORATIVE FILTERING model for existing user {user_id}")
        if not self.loaded:
            self.load_models()
        
        # Check if CF model exists
        if self.cf_model is None:
            return []
        
        # Check structure: expect U, Vt, user_ids, course_ids from SVD model
        if 'user_ids' not in self.cf_model or 'course_ids' not in self.cf_model:
            return []
        
        # Check if user exists in training data
        try:
            user_idx = self.cf_model['user_ids'].index(user_id)
        except (ValueError, AttributeError):
            return []
        
        # Get predicted scores: U @ Sigma @ Vt
        # U shape: (n_users, k), Vt shape: (k, n_items)
        user_factors = self.cf_model['U'][user_idx]  # shape (k,)
        sigma = self.cf_model.get('sigma', np.eye(self.cf_model['U'].shape[1]))  # shape (k, k)
        item_factors = self.cf_model['Vt']  # shape (k, n_items)
        
        # predicted_scores = user_factors @ sigma @ item_factors
        predicted_scores = user_factors @ sigma @ item_factors  # shape (n_items,)
        
        # Get top-k programs
        top_indices = predicted_scores.argsort()[-k:][::-1]
        
        course_ids = self.cf_model['course_ids']
        raw_scores = []
        chosen = []
        
        for idx in top_indices:
            if 0 <= idx < len(course_ids):
                program_id = str(course_ids[idx])
                score = float(predicted_scores[idx])
                chosen.append((program_id, score))
                raw_scores.append(score)

        norm_scores = self._normalize_scores_0_1(raw_scores)
        recommendations = []
        for (program_id, _raw), score01 in zip(chosen, norm_scores):
            matches = self.programs_df[self.programs_df['program_id'].astype(str) == str(program_id)]
            if len(matches) > 0:
                program = matches.iloc[0]
                explanation = "Users with similar interests also liked this program."
                recommendations.append((str(program_id), float(score01), explanation))
        
        return recommendations
    
    def new_user_collaborative_recommendations(
        self,
        user_interests: str,
        k: int = 5
    ) -> List[Tuple[str, float, str]]:
        """Generate collaborative-style recommendations for new users using content-based profile."""
        print("[RECOMMENDER] Using NEW USER COLLABORATIVE FILTERING (simulated CF for new user)")
        if not self.loaded:
            self.load_models()
        
        # Check if CF model exists
        if self.cf_model is None or self.tfidf_vectorizer is None:
            return []
        
        # Check structure
        if 'course_ids' not in self.cf_model or 'Vt' not in self.cf_model:
            return []
        
        # Create user profile vector from interests
        user_vector = self.tfidf_vectorizer.transform([str(user_interests).lower().replace(",", " ")])
        
        # Find similar programs based on content
        similarities = cosine_similarity(user_vector, self.tfidf_matrix).flatten()
        
        # Get top programs user would likely rate highly
        top_program_indices = similarities.argsort()[-20:][::-1]
        
        # Create a pseudo user factor by averaging the item factors of similar programs
        # This simulates what the user's latent factors might be
        if len(top_program_indices) > 0:
            course_ids = self.cf_model['course_ids']
            item_factors_t = self.cf_model['Vt']  # shape (k, n_items)
            sigma = self.cf_model.get('sigma', np.eye(item_factors_t.shape[0]))
            valid_factors = []
            
            for prog_idx in top_program_indices[:10]:  # Use top 10 similar programs
                program_id = str(self.programs_df.iloc[prog_idx]['program_id'])
                try:
                    item_idx = course_ids.index(int(program_id))
                    # Extract column from Vt
                    valid_factors.append(item_factors_t[:, item_idx])
                except (ValueError, IndexError):
                    continue
            
            if valid_factors:
                # Average the factors to create user profile
                pseudo_user_factor = np.mean(valid_factors, axis=0)  # shape (k,)
                
                # Predict scores for all programs: user_factor @ sigma @ Vt
                predicted_scores = pseudo_user_factor @ sigma @ item_factors_t  # shape (n_items,)
                
                # Get top-k programs
                top_indices = predicted_scores.argsort()[-k:][::-1]
                
                raw_scores = []
                chosen = []
                for idx in top_indices:
                    if 0 <= idx < len(course_ids):
                        program_id = str(course_ids[idx])
                        score = float(predicted_scores[idx])
                        chosen.append((program_id, score))
                        raw_scores.append(score)

                norm_scores = self._normalize_scores_0_1(raw_scores)
                recommendations = []
                for (program_id, _raw), score01 in zip(chosen, norm_scores):
                    matches = self.programs_df[self.programs_df['program_id'].astype(str) == str(program_id)]
                    if len(matches) > 0:
                        program = matches.iloc[0]
                        explanation = "Based on your interests, users with similar profiles have enjoyed this program."
                        recommendations.append((str(program_id), float(score01), explanation))
                
                return recommendations
        
        return []
    
    def hybrid_recommendations(
        self, 
        user_interests: str, 
        user_id: str = None,
        k: int = 5
    ) -> List[Dict]:
        """Generate hybrid recommendations combining content and CF."""
        print(f"[RECOMMENDER] Using HYBRID model (user_id={user_id})")
        if not self.loaded:
            self.load_models()
        
        # Get content-based recommendations
        content_recs = self.content_based_recommendations(user_interests, k=20)
        content_scores = {str(pid): float(score) for pid, score, _ in content_recs}
        content_explanations = {str(pid): exp for pid, _, exp in content_recs}
        
        # Get collaborative recommendations
        cf_scores = {}
        if user_id:
            # Existing user: use their interaction history
            cf_recs = self.collaborative_recommendations(user_id, k=20)
            cf_scores = {str(pid): float(score) for pid, score, _ in cf_recs}
        else:
            # New user: use simulated CF based on interests
            cf_recs = self.new_user_collaborative_recommendations(user_interests, k=20)
            cf_scores = {str(pid): float(score) for pid, score, _ in cf_recs}
        
        # Combine scores
        all_programs = set(content_scores.keys()) | set(cf_scores.keys())
        hybrid_scores = {}
        
        for program_id in all_programs:
            content_score = content_scores.get(program_id, 0)
            cf_score = cf_scores.get(program_id, 0)
            
            # Normalize CF scores if they exist
            if cf_scores:
                max_cf = max(cf_scores.values()) if cf_scores else 1
                cf_score_norm = cf_score / max_cf if max_cf > 0 else 0
            else:
                cf_score_norm = 0
            
            # Weighted average
            if cf_scores:
                hybrid_score = (HYBRID_CONTENT_WEIGHT * float(content_score) + 
                               HYBRID_CF_WEIGHT * float(cf_score_norm))
            else:
                # Fallback if CF completely failed
                hybrid_score = float(content_score)
            
            hybrid_scores[program_id] = hybrid_score
        
        # Sort by hybrid score and get top-k
        # Filter out programs with very low scores (less relevant)
        sorted_programs = sorted(hybrid_scores.items(), key=lambda x: x[1], reverse=True)
        # Only include programs with meaningful scores (> 0.01 for content-based threshold)
        filtered_programs = [(pid, score) for pid, score in sorted_programs if score > 0.01]
        top_programs = filtered_programs[:k] if len(filtered_programs) >= k else filtered_programs
        
        # If we don't have enough, fill with top scored ones anyway
        if len(top_programs) < k:
            top_programs = sorted_programs[:k]
        
        # Build recommendation list with full details
        recommendations = []
        for program_id, score in top_programs:
            program = self.programs_df[self.programs_df['program_id'].astype(str) == str(program_id)].iloc[0]
            
            # Use content explanation or create hybrid explanation
            explanation = content_explanations.get(program_id, 
                "Recommended based on your interests and similar user preferences.")
            
            recommendations.append({
                'program_id': str(program_id),
                'program_name': program['name'],
                'description': program['description'],
                'skills': program.get('tags_text', program.get('skills', '')),
                'score': float(score),
                'explanation': explanation
            })
        
        return recommendations
    
    def _generate_content_explanation(self, user_interests: str, program: pd.Series) -> str:
        """Generate human-readable explanation for content-based recommendation."""
        interests_list = self._parse_interests_tokens(user_interests)
        program_text = program.get('text', '').lower()
        program_tags = program.get('tags_text', '').lower()
        
        # Find matching interests in program text
        matches = []
        for interest in interests_list:
            # Check if interest appears in program text
            if interest in program_text:
                matches.append(interest)
        
        if matches:
            if len(matches) == 1:
                matched_text = matches[0]
            elif len(matches) == 2:
                matched_text = f"{matches[0]} and {matches[1]}"
            else:
                matched_text = f"{matches[0]}, {matches[1]}, and others"
                
            return f"Recommended because you're interested in {matched_text}, and this program focuses on {program.get('tags_text', '')}."
        else:
            return f"This program focuses on {program.get('tags_text', '')}, which may align with your background and interests."


# Global instance
engine = RecommendationEngine()
