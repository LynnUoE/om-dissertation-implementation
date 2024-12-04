# researcher_analyzer.py
import json
import requests
from typing import Dict, Optional

class ResearcherAnalyzer:
    def __init__(self, openai_api_key: str):
        self.openai_api_key = openai_api_key
        self.openai_headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {openai_api_key}'
        }

    def analyze_researcher_fit(self, researcher_data: Dict, query_requirements: Dict) -> Dict:
        """
        Analyze how well a researcher fits the query requirements.
        """
        # Extract researcher information
        concepts = researcher_data.get('x_concepts', [])
        works_count = researcher_data.get('works_count', 0)
        cited_by_count = researcher_data.get('cited_by_count', 0)
        recent_works = researcher_data.get('recent_works', [])
        
        # Create a detailed prompt for analysis
        prompt = f"""Analyze this researcher's fit for the specified requirements:

        QUERY REQUIREMENTS:
        Disciplines Required: {json.dumps(query_requirements.get('disciplines', []), indent=2)}
        Must-Have Criteria: {query_requirements.get('search_criteria', {}).get('must_have', [])}
        Preferred Criteria: {query_requirements.get('search_criteria', {}).get('preferred', [])}
        Research Focus: {query_requirements.get('research_focus', {})}

        RESEARCHER PROFILE:
        Expertise Areas: {[concept['display_name'] for concept in concepts[:5]] if concepts else 'No concepts available'}
        Publication Record: {works_count} total publications
        Citation Impact: {cited_by_count} total citations
        Recent Works: {[work.get('title') for work in recent_works[:3]] if recent_works else 'No recent works available'}

        Please analyze the researcher's fit and provide:
        1. A numerical match score (0-100) based on alignment with requirements
        2. Detailed justification for the score
        3. Key strengths matching the requirements
        4. Any gaps or limitations
        5. Potential for interdisciplinary contribution
        6. Recommendation for collaboration potential

        Format the response as JSON:
        {{
            "match_score": number,
            "justification": "detailed explanation",
            "strengths": [
                {{
                    "area": "strength area",
                    "description": "detailed description",
                    "relevance": "high/medium/low"
                }}
            ],
            "gaps": [
                {{
                    "area": "gap area",
                    "impact": "description of impact",
                    "mitigation": "possible mitigation"
                }}
            ],
            "interdisciplinary_potential": {{
                "level": "high/medium/low",
                "description": "detailed description",
                "opportunities": ["opportunity1", "opportunity2"]
            }},
            "collaboration_recommendation": {{
                "recommendation": "recommend/consider/caution",
                "reasoning": "detailed explanation"
            }}
        }}
        """
        
        return self._get_llm_analysis(prompt)

    def generate_expertise_summary(self, researcher_data: Dict, analysis_results: Dict) -> str:
        """
        Generate a comprehensive expertise summary for the researcher.
        """
        # Extract detailed information
        recent_works = researcher_data.get('recent_works', [])
        concepts = researcher_data.get('x_concepts', [])
        
        prompt = f"""Create a comprehensive expertise summary for this researcher:

        RESEARCHER BACKGROUND:
        Publications: {researcher_data.get('works_count')} total works
        Citations: {researcher_data.get('cited_by_count')} total citations
        Primary Concepts: {[c['display_name'] for c in concepts[:5]] if concepts else 'No concepts available'}
        
        RECENT PUBLICATIONS:
        {json.dumps([{
            'title': work.get('title'),
            'year': work.get('publication_year'),
            'type': work.get('type')
        } for work in recent_works[:3]], indent=2) if recent_works else 'No recent works available'}

        ANALYSIS RESULTS:
        Match Score: {analysis_results.get('match_score')}
        Key Strengths: {json.dumps(analysis_results.get('strengths', []), indent=2)}
        Interdisciplinary Potential: {json.dumps(analysis_results.get('interdisciplinary_potential', {}), indent=2)}

        Please provide a comprehensive summary including:
        1. Expert Profile Overview (2-3 sentences capturing key expertise)
        2. Core Research Areas (with depth of expertise)
        3. Impact Assessment (quality and influence of work)
        4. Collaboration Potential (based on interdisciplinary work)
        5. Current Research Trajectory
        6. Notable Achievements or Specializations

        Format the response as JSON:
        {{
            "profile_summary": "concise overview",
            "core_expertise": [
                {{
                    "area": "expertise area",
                    "depth": "depth assessment",
                    "evidence": "supporting evidence"
                }}
            ],
            "research_impact": {{
                "overall_assessment": "impact description",
                "key_contributions": ["contribution1", "contribution2"],
                "field_influence": "description of influence"
            }},
            "collaboration_potential": {{
                "strengths": ["strength1", "strength2"],
                "opportunities": ["opportunity1", "opportunity2"]
            }},
            "research_trajectory": {{
                "current_focus": "description",
                "emerging_interests": ["interest1", "interest2"],
                "future_potential": "assessment"
            }},
            "achievements": [
                {{
                    "type": "achievement type",
                    "description": "detailed description",
                    "significance": "significance assessment"
                }}
            ]
        }}
        """
        
        return self._get_llm_analysis(prompt)

    def _get_llm_analysis(self, prompt: str) -> Dict:
        """
        Helper method to make OpenAI API calls.
        """
        try:
            data = {
                'model': 'gpt-3.5-turbo',
                'messages': [
                    {
                        'role': 'system',
                        'content': 'You are a specialized academic research analyst with expertise in evaluating research profiles and academic expertise.'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'temperature': 0.7,
                'max_tokens': 800
            }

            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                json=data,
                headers=self.openai_headers
            )

            if response.status_code == 200:
                content = response.json()['choices'][0]['message']['content']
                return json.loads(content)
            else:
                print(f"OpenAI API error: {response.status_code}")
                return {}

        except Exception as e:
            print(f"Error in OpenAI API call: {str(e)}")
            return {}

# Example usage
def main():
    OPENAI_API_KEY = 'your-openai-api-key'
    analyzer = ResearcherAnalyzer(OPENAI_API_KEY)
    
    # Example researcher data and query requirements
    researcher_data = {
        'works_count': 150,
        'cited_by_count': 5000,
        'x_concepts': [
            {'display_name': 'Machine Learning'},
            {'display_name': 'Artificial Intelligence'},
            {'display_name': 'Computer Vision'}
        ],
        'recent_works': [
            {'title': 'Deep Learning in Medical Imaging', 'publication_year': 2023},
            {'title': 'AI for Healthcare Applications', 'publication_year': 2022}
        ]
    }
    
    query_requirements = {
        'disciplines': [
            {'name': 'Computer Science', 'importance': 'high'},
            {'name': 'Healthcare', 'importance': 'high'}
        ],
        'search_criteria': {
            'must_have': ['machine learning expertise'],
            'preferred': ['healthcare experience']
        }
    }
    
    # Analyze researcher
    fit_analysis = analyzer.analyze_researcher_fit(researcher_data, query_requirements)
    print("\nFit Analysis:")
    print(json.dumps(fit_analysis, indent=2))
    
    # Generate summary
    summary = analyzer.generate_expertise_summary(researcher_data, fit_analysis)
    print("\nExpertise Summary:")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
    