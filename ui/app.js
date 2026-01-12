// API Configuration
const API_BASE_URL = 'http://127.0.0.1:8000';

// Skills data
let availableSkills = [];
let selectedSkills = [];

// Load skills on page load
async function loadSkills() {
    try {
        const response = await fetch('filtered_skills.txt');
        const text = await response.text();
        availableSkills = text.split('\n')
            .map(skill => skill.trim())
            .filter(skill => skill.length > 0)
            .sort();
        console.log(`✓ Loaded ${availableSkills.length} skills`);
        populateSkillSelect();
    } catch (error) {
        console.error('⚠️ Error loading skills file, using fallback list:', error);
        // Fallback to comprehensive skills list
        availableSkills = [
            'python', 'javascript', 'java', 'c++', 'data analysis', 'machine learning',
            'web development', 'mobile development', 'design', 'marketing', 'adobe photoshop',
            'project management', 'business', 'finance', 'writing', 'communication',
            'leadership', 'research', 'biology', 'chemistry', 'physics', 'mathematics',
            'statistics', 'economics', 'accounting', 'management', 'sales', 'creativity',
            'problem solving', 'critical thinking', 'teamwork', 'public speaking',
            'social media', 'content creation', 'video editing', 'graphic design',
            'ui/ux design', 'database', 'sql', 'cloud computing', 'cybersecurity',
            'artificial intelligence', 'deep learning', 'neural networks', 'computer vision',
            'natural language processing', 'robotics', 'embedded systems', 'electronics',
            'mechanical engineering', 'civil engineering', 'architecture', 'art history',
            'music theory', 'film production', 'photography', 'creative writing'
        ].sort();
        console.log(`✓ Using ${availableSkills.length} fallback skills`);
        populateSkillSelect();
    }
}

// Initialize on page load
loadSkills();

// DOM Elements
const form = document.getElementById('recommendation-form');
const inputSection = document.getElementById('input-section');
const resultsSection = document.getElementById('results-section');
const loading = document.getElementById('loading');
const errorMessage = document.getElementById('error-message');
const errorText = document.getElementById('error-text');
const recommendationsContainer = document.getElementById('recommendations-container');
const resetBtn = document.getElementById('reset-btn');
const submitBtn = document.getElementById('submit-btn');

// Skill input elements
const skillSelect = document.getElementById('skill-select');
const experienceSelect = document.getElementById('experience-select');
const addSkillBtn = document.getElementById('add-skill-btn');
const selectedSkillsContainer = document.getElementById('selected-skills');
const interestsHiddenInput = document.getElementById('interests');

// Populate skill select dropdown
function populateSkillSelect() {
    availableSkills.forEach(skill => {
        const option = document.createElement('option');
        option.value = skill;
        option.textContent = skill;
        skillSelect.appendChild(option);
    });
}

// Add skill button click handler
addSkillBtn.addEventListener('click', () => {
    const skillName = skillSelect.value;
    const experienceLevel = parseInt(experienceSelect.value);
    
    if (!skillName) {
        return;
    }
    
    addSkill(skillName, experienceLevel);
    
    // Reset selects
    skillSelect.value = '';
    experienceSelect.value = '3';
    
    // Update select options to hide added skill
    updateSkillSelectOptions();
});

// Update skill select options to hide already selected skills
function updateSkillSelectOptions() {
    Array.from(skillSelect.options).forEach(option => {
        if (option.value && selectedSkills.some(s => s.name === option.value)) {
            option.style.display = 'none';
        } else {
            option.style.display = '';
        }
    });
}

// Add skill with experience level
function addSkill(skillName, experienceLevel = 3) {
    // Check if already added
    if (selectedSkills.some(s => s.name === skillName)) {
        return;
    }
    
    // Add to selected skills
    selectedSkills.push({
        name: skillName,
        experience: experienceLevel
    });
    
    renderSelectedSkills();
    updateInterestsInput();
}

// Remove skill
function removeSkill(skillName) {
    selectedSkills = selectedSkills.filter(s => s.name !== skillName);
    renderSelectedSkills();
    updateInterestsInput();
    updateSkillSelectOptions();
}

// Update skill experience
function updateSkillExperience(skillName, newExperience) {
    const skill = selectedSkills.find(s => s.name === skillName);
    if (skill) {
        skill.experience = parseInt(newExperience);
        updateInterestsInput();
    }
}

// Render selected skills
function renderSelectedSkills() {
    if (selectedSkills.length === 0) {
        selectedSkillsContainer.innerHTML = '<div class="no-skills-message">No skills selected yet. Choose a skill and click + to add.</div>';
        return;
    }
    
    const experienceLabels = {
        1: '🌱 Beginner',
        2: '📚 Basic',
        3: '💼 Intermediate',
        4: '🚀 Advanced',
        5: '⭐ Expert'
    };
    
    selectedSkillsContainer.innerHTML = selectedSkills.map(skill => `
        <div class="skill-tag">
            <span class="skill-tag-name">${skill.name}</span>
            <span class="skill-tag-level">${experienceLabels[skill.experience]}</span>
            <button type="button" class="skill-tag-remove" onclick="removeSkill('${skill.name}')">&times;</button>
        </div>
    `).join('');
}

// Update hidden interests input
function updateInterestsInput() {
    // Create weighted interest string based on experience levels
    const weightedSkills = selectedSkills.map(skill => {
        // Repeat skill name based on experience level for more weight
        return Array(skill.experience).fill(skill.name).join(' ');
    }).join(', ');
    
    interestsHiddenInput.value = weightedSkills;
}

// Grade inputs - update display on change
const gradeInputs = document.querySelectorAll('input[type="number"]');
gradeInputs.forEach(input => {
    input.addEventListener('input', (e) => {
        const display = e.target.nextElementSibling;
        if (display && display.classList.contains('grade-display')) {
            display.textContent = `${e.target.value}%`;
        }
    });
});

// Form submission
form.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    // Get form data
    const formData = new FormData(form);
    const interests = formData.get('interests');
    const k = parseInt(formData.get('k'));
    const modelType = formData.get('model_type') || 'hybrid';
    
    // Validate
    if (!interests.trim()) {
        showError('Please add at least one skill with experience level');
        return;
    }
    
    if (selectedSkills.length === 0) {
        showError('Please add at least one skill with experience level');
        return;
    }
    
    // Prepare request
    const requestBody = {
        interests: interests
    };
    
    // Show loading
    inputSection.classList.add('hidden');
    resultsSection.classList.add('hidden');
    errorMessage.classList.add('hidden');
    loading.classList.remove('hidden');
    
    try {
        // Call API with selected model
        const response = await fetch(`${API_BASE_URL}/recommend?k=${k}&approach=${modelType}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to get recommendations');
        }
        
        const data = await response.json();
        
        // Display results with model info
        displayRecommendations(data.recommendations, data.approach || modelType);
        
        // Update footer with model used
        updateFooter(data.approach || modelType);
        
        // Hide loading, show results
        loading.classList.add('hidden');
        resultsSection.classList.remove('hidden');
        
    } catch (error) {
        console.error('Error:', error);
        loading.classList.add('hidden');
        showError(error.message);
    }
});

// Display recommendations
function displayRecommendations(recommendations, approach) {
    recommendationsContainer.innerHTML = '';
    
    // Display user skills summary
    displayUserSkills();
    
    // Add model info banner
    const modelInfo = document.createElement('div');
    modelInfo.className = 'model-info-banner';
    const modelNames = {
        'hybrid': '🔀 Hybrid Model (Content-Based + Collaborative)',
        'content-based': '📚 Content-Based Model (TF-IDF Feature Matching)',
        'collaborative': '👥 Collaborative Filtering (SVD Matrix Factorization)'
    };
    modelInfo.innerHTML = `
        <strong>Model Used:</strong> ${modelNames[approach] || approach}
    `;
    recommendationsContainer.appendChild(modelInfo);
    
    recommendations.forEach((rec, index) => {
        const card = createRecommendationCard(rec, index + 1);
        recommendationsContainer.appendChild(card);
    });
}

// Display user skills summary
function displayUserSkills() {
    const skillsDisplay = document.getElementById('user-skills-display');
    if (!skillsDisplay || selectedSkills.length === 0) return;
    
    const experienceLabels = {
        1: '🌱 Beginner',
        2: '📚 Basic',
        3: '💼 Intermediate',
        4: '🚀 Advanced',
        5: '⭐ Expert'
    };
    
    const skillsHTML = selectedSkills.map(skill => {
        return `<div class="user-skill-item">
            <span class="user-skill-name">${skill.name}</span>
            <span class="user-skill-level">${experienceLabels[skill.experience]}</span>
        </div>`;
    }).join('');
    
    skillsDisplay.innerHTML = `
        <div class="user-skills-header">
            <h3>📋 Your Skills Profile</h3>
        </div>
        <div class="user-skills-list">
            ${skillsHTML}
        </div>
    `;
}

// Create recommendation card
function createRecommendationCard(rec, rank) {
    const card = document.createElement('div');
    card.className = 'recommendation-card';
    
    // Parse skills into tags
    const skills = rec.skills.split(' ').filter(s => s.trim());

    const shortDescription = truncateSentences(rec.description, 3);
    
    const ratingStars = rec.course_rating ? '⭐'.repeat(Math.round(rec.course_rating)) : '';
    const ratingText = rec.course_rating ? `${rec.course_rating}/5` : 'N/A';
    
    card.innerHTML = `
        <div class="recommendation-header">
            <div>
                <div style="font-size: 0.875rem; color: var(--text-secondary); font-weight: 600;">
                    #${rank} RECOMMENDATION
                </div>
                <h3 class="program-title">${rec.program_name}</h3>
                ${rec.course_rating ? `<div style="font-size: 0.9rem; color: var(--warning); margin: 0.25rem 0;">${ratingStars} <span style="color: var(--text-secondary);">${ratingText}</span></div>` : ''}
                <p class="program-description">${shortDescription}</p>
            </div>
            <div class="score-badge">
                ${(rec.score * 100).toFixed(0)}% Match
            </div>
        </div>
        
        <div class="skills-tags">
            ${skills.map(skill => `<span class="skill-tag">${skill}</span>`).join('')}
        </div>
        
        <div class="explanation">
            💡 ${rec.explanation}
        </div>
        
        <div class="feedback-buttons">
            ${rec.course_url ? `<a href="${rec.course_url}" target="_blank" class="feedback-btn" style="text-decoration: none; display: inline-block;">
                🔗 View Course
            </a>` : ''}
            <button class="feedback-btn" onclick="submitFeedback('${rec.program_id}', 'clicked', this)">
                👍 Interested
            </button>
            <button class="feedback-btn" onclick="submitFeedback('${rec.program_id}', 'rejected', this)">
                👎 Not for me
            </button>
        </div>
    `;
    
    return card;
}

function truncateSentences(text, maxSentences = 3) {
    if (text === null || text === undefined) return '';
    const clean = String(text).replace(/\s+/g, ' ').trim();
    if (!clean) return '';

    const matches = clean.match(/[^.!?]+[.!?]+(?=\s|$)|[^.!?]+$/g) || [];
    const sentences = matches.map(s => s.trim()).filter(Boolean);

    if (sentences.length <= maxSentences) return clean;
    return `${sentences.slice(0, maxSentences).join(' ').trim()} ...`;
}

// Submit feedback
async function submitFeedback(programId, feedbackType, button) {
    try {
        const response = await fetch(`${API_BASE_URL}/feedback`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                program_id: programId,
                feedback_type: feedbackType
            })
        });
        
        if (response.ok) {
            // Update button state
            const buttons = button.parentElement.querySelectorAll('.feedback-btn');
            buttons.forEach(btn => {
                btn.classList.remove('clicked', 'rejected');
            });
            button.classList.add(feedbackType);
            
            // Show confirmation
            const originalText = button.textContent;
            button.textContent = '✓ Recorded';
            setTimeout(() => {
                button.textContent = originalText;
            }, 2000);
        }
    } catch (error) {
        console.error('Feedback error:', error);
    }
}

// Reset form
resetBtn.addEventListener('click', () => {
    resultsSection.classList.add('hidden');
    inputSection.classList.remove('hidden');
    form.reset();
    // Clear selected skills
    selectedSkills = [];
    renderSelectedSkills();
    // Reset skill select options to show all skills
    updateSkillSelectOptions();
});

// Show error
function showError(message) {
    errorText.textContent = message;
    errorMessage.classList.remove('hidden');
    inputSection.classList.add('hidden');
    resultsSection.classList.add('hidden');
}

// Test cases
const testCases = {
    cs: {
        skills: [
            { name: 'python', experience: 4 },
            { name: 'machine learning', experience: 3 },
            { name: 'data analysis', experience: 3 },
            { name: 'algorithms', experience: 3 }
        ]
    },
    bio: {
        skills: [
            { name: 'biology', experience: 4 },
            { name: 'research', experience: 3 },
            { name: 'chemistry', experience: 3 },
            { name: 'genetics', experience: 2 }
        ]
    },
    business: {
        skills: [
            { name: 'finance', experience: 3 },
            { name: 'marketing', experience: 3 },
            { name: 'management', experience: 2 },
            { name: 'economics', experience: 3 }
        ]
    },
    arts: {
        skills: [
            { name: 'design', experience: 4 },
            { name: 'adobe photoshop', experience: 4 },
            { name: 'creativity', experience: 4 },
            { name: 'visual communication', experience: 3 }
        ]
    },
    engineering: {
        skills: [
            { name: 'engineering', experience: 3 },
            { name: 'mathematics', experience: 4 },
            { name: 'physics', experience: 4 },
            { name: 'problem solving', experience: 4 }
        ]
    }
};

// Fill test case
function fillTestCase(testName) {
    const test = testCases[testName];
    if (!test) return;
    
    // Clear existing skills
    selectedSkills = [];
    
    // Add test skills
    test.skills.forEach(skill => {
        addSkill(skill.name, skill.experience);
    });
    
    // Scroll to form
    document.getElementById('input-section').scrollIntoView({ behavior: 'smooth', block: 'center' });
    
    // Highlight form briefly
    const form = document.getElementById('recommendation-form');
    form.style.border = '2px solid var(--primary)';
    setTimeout(() => {
        form.style.border = '';
    }, 1500);
}

// Update footer with model information
function updateFooter(approach) {
    const footerText = document.getElementById('footer-text');
    const modelNames = {
        'hybrid': 'Hybrid Recommendation System (Content-Based + Collaborative)',
        'content-based': 'Content-Based Recommendation (TF-IDF)',
        'collaborative': 'Collaborative Filtering (SVD Matrix Factorization)'
    };
    footerText.textContent = `Powered by ${modelNames[approach] || 'Hybrid Recommendation System'}`;
}

// Hide error
function hideError() {
    errorMessage.classList.add('hidden');
    inputSection.classList.remove('hidden');
}

// Check API health on load
window.addEventListener('load', async () => {
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        if (!response.ok) {
            showError('API server is not responding. Please make sure the server is running.');
        }
    } catch (error) {
        showError('Cannot connect to API server. Please start the server with: python -m uvicorn app.main:app --reload');
    }
});
