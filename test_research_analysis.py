# Initialize analyzer
analyzer = ResearcherAnalyzer(OPENAI_API_KEY)

# Analyze researcher
fit_analysis = analyzer.analyze_researcher_fit(researcher_data, query_requirements)

# Generate summary
expertise_summary = analyzer.generate_expertise_summary(researcher_data, fit_analysis)