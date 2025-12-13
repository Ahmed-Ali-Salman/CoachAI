"""UI-facing agent orchestration (Streamlit layer)."""

import streamlit as st

from coachai.services.coach_service import CoachService


class LearningCoachAgent:
    def __init__(self, config):
        self.config = config
        self.service = CoachService(config)

        self.knowledge_repo = self.service.knowledge_repo
        self.model_handler = self.service.model_handler

    def initialize(self):
        ok = self.service.initialize()
        if not ok and getattr(self.config, 'USE_REMOTE_MODEL', False):
            st.error('Failed to initialize remote model. Check MISTRAL_API_KEY and connectivity.')
        return ok

    def process_query(self, text_query=None, image=None, image_type="General Text"):
        if image is not None:
            with st.spinner("🔍 Analyzing image..."):
                if image_type == "Math Equations":
                    st.success("🔢 Math content detected - enhanced mathematical analysis enabled")
                elif image_type == "Diagram/Chart":
                    st.success("📊 Diagram/chart detected - visual analysis optimized")
                elif image_type == "Handwritten Notes":
                    st.success("✍️ Handwritten content detected - handwriting recognition enabled")

        combined_query = text_query or ""

        if not combined_query and image is None:
            return None, None, None

        if not combined_query and image is not None:
            if image_type == "Math Equations":
                combined_query = "This image contains mathematical equations and formulas. Carefully analyze the mathematical symbols, variables, and relationships shown. Explain the mathematical concepts, solve any equations visible, and provide step-by-step reasoning. Identify what branch of mathematics this relates to (algebra, geometry, calculus, etc.) and explain the underlying principles."
            elif image_type == "Diagram/Chart":
                combined_query = "This image contains a diagram, chart, or visual representation. Analyze the visual elements, labels, relationships, and data shown. Explain what concepts are being illustrated, how the visual elements represent relationships, and what educational principles or processes are being demonstrated."
            elif image_type == "Handwritten Notes":
                combined_query = "This image contains handwritten notes about educational concepts. Carefully examine the writing, symbols, and content. Explain the concepts mentioned, any formulas or diagrams shown, and provide a clear educational explanation of the subject matter covered in these notes. Determine the academic subject (mathematics, science, etc.) and explain the key principles."
            else:
                combined_query = "Please analyze this image and provide an explanation of any educational or academic content visible, including text, diagrams, equations, or concepts from any subject area."

        with st.spinner("🔍 Finding relevant knowledge..."):
            relevant_lessons = self.service.find_relevant(
                combined_query,
                top_k=self.config.TOP_K
            )

            needs_content_boost = (
                len(relevant_lessons) < 2 and image_type in ["Math Equations", "Handwritten Notes", "Diagram/Chart"]
            ) or (
                image is not None and len(relevant_lessons) > 0 and len(relevant_lessons) < self.config.TOP_K
            )

            if needs_content_boost:
                available_subjects = set(lesson.get('subject', '').lower() for lesson in self.knowledge_repo.all())
                subject_keywords = {
                    'mathematics': ['math', 'algebra', 'geometry', 'calculus', 'equation', 'formula', 'theorem', 'proof'],
                    'physics': ['physics', 'force', 'mass', 'acceleration', 'velocity', 'energy', 'motion', 'newton', 'law'],
                    'biology': ['biology', 'cell', 'photosynthesis', 'organism', 'life', 'dna', 'protein', 'evolution'],
                    'chemistry': ['chemistry', 'atom', 'molecule', 'reaction', 'acid', 'base', 'compound', 'element']
                }

                boost_terms = []
                if image_type == "Math Equations":
                    boost_terms = ["mathematics algebra geometry calculus equation formula"]
                    if 'physics' in available_subjects:
                        boost_terms.append("physics mechanics kinematics")
                elif image_type == "Handwritten Notes":
                    for subject in available_subjects:
                        if subject in subject_keywords:
                            boost_terms.append(f"{subject} {' '.join(subject_keywords[subject][:5])}")
                elif image_type == "Diagram/Chart":
                    boost_terms = ["diagram chart graph visual representation illustration"]
                    for subject in available_subjects:
                        if subject in subject_keywords:
                            boost_terms.append(f"{subject} diagram {' '.join(subject_keywords[subject][:3])}")

                all_boosted_lessons = []
                for boost_term in boost_terms[:3]:
                    boost_query = combined_query + " " + boost_term
                    boosted_results = self.service.find_relevant(
                        boost_query, top_k=self.config.TOP_K
                    )
                    all_boosted_lessons.extend(boosted_results)

                all_lessons = relevant_lessons + all_boosted_lessons
                seen_topics = set()
                deduplicated = []
                for lesson in all_lessons:
                    topic_key = lesson.get('topic', '').lower().strip()
                    if topic_key and topic_key not in seen_topics:
                        seen_topics.add(topic_key)
                        try:
                            if image_type == "Math Equations" and 'math' in (lesson.get('subject') or '').lower():
                                lesson['similarity'] = min(float(lesson.get('similarity', 0)) * 1.3, 1.0)
                        except Exception:
                            pass
                        deduplicated.append(lesson)

                if image_type in ["Math Equations", "Handwritten Notes"]:
                    subject_relevant = []
                    other_lessons = []

                    for lesson in deduplicated:
                        is_relevant = False
                        lesson_subject = (lesson.get('subject') or '').lower()

                        if image_type == "Math Equations" and 'math' in lesson_subject:
                            is_relevant = True
                        elif image_type == "Handwritten Notes":
                            is_relevant = True

                        if is_relevant:
                            subject_relevant.append(lesson)
                        else:
                            other_lessons.append(lesson)

                    subject_relevant.sort(key=lambda x: x.get('similarity', 0), reverse=True)
                    other_lessons.sort(key=lambda x: x.get('similarity', 0), reverse=True)

                    relevant_count = min(len(subject_relevant), self.config.TOP_K - 1)
                    other_count = min(len(other_lessons), self.config.TOP_K - relevant_count)

                    relevant_lessons = subject_relevant[:relevant_count] + other_lessons[:other_count]
                else:
                    deduplicated.sort(key=lambda x: x.get('similarity', 0), reverse=True)
                    relevant_lessons = deduplicated[:self.config.TOP_K]

        return relevant_lessons, combined_query, None

    def generate_explanation(self, query: str, relevant_lessons, image=None):
        return self.service.generate_explanation(query, relevant_lessons, image=image)

    def generate_practice_question(self, topic: str):
        return self.service.generate_practice_question(topic)

    def evaluate_answer(self, question: str, student_answer: str, correct_concept: str):
        return self.service.evaluate_answer(question, student_answer, correct_concept)
