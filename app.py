"""
Multimodal Learning Coach - Streamlit Application
Run with: streamlit run app.py
"""
import os
# Reduce TensorFlow logging
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

import streamlit as st
from PIL import Image

# Import from modular components
from coachai.core.config import Config
from ui.image_processor import ImageProcessor
from ui.learning_coach_agent import LearningCoachAgent
from coachai.clients.supabase_client import SupabaseClient


def main():
    config = Config()
    
    st.set_page_config(
        page_title="🎓 Multimodal Learning Coach",
        page_icon="🎓",
        layout="wide"
    )
    
    st.title("🎓 Multimodal Learning Coach")
    st.markdown(f"""
    Powered by **{config.MODEL_NAME}**
    - Ask questions • Upload images • Get explanations • Practice
    """)

    # Initialize session state for operation control
    if 'operation_running' not in st.session_state:
        st.session_state.operation_running = False
    if 'operation_type' not in st.session_state:
        st.session_state.operation_type = None
    if 'stop_requested' not in st.session_state:
        st.session_state.stop_requested = False

    # Initialize
    if 'agent' not in st.session_state:
        with st.spinner("Loading..."):
            st.session_state.agent = LearningCoachAgent(config)
            if not st.session_state.agent.initialize():
                st.error("Failed to load model. Check path in config.")
                st.stop()

    agent = st.session_state.agent

    # Compatibility helper: some Streamlit versions lack `experimental_rerun`.
    def safe_rerun():
        try:
            st.experimental_rerun()
        except Exception:
            # Fallback: toggle a session-state flag and stop to force a rerun on next interaction
            st.session_state['_rerun_toggle'] = not st.session_state.get('_rerun_toggle', False)
            try:
                st.stop()
            except Exception:
                return

    # Show operation status after initialization
    if st.session_state.operation_running:
        st.warning(f"🔄 {st.session_state.operation_type} in progress... Use the stop button in the sidebar to cancel.")
    
    # Sidebar
    with st.sidebar:
        # Authentication (Supabase) - lightweight auth UI
        st.header("🔐 Account")
        sup = None
        try:
            sup = SupabaseClient()
        except Exception:
            sup = None

        if sup:
            if 'user_id' not in st.session_state:
                st.markdown("**Sign in / Sign up**")
                email = st.text_input("Email", key='auth_email')
                password = st.text_input("Password", type='password', key='auth_password')
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Sign In"):
                            try:
                                resp = sup.auth_sign_in(email, password)
                                user = resp.get('user') or getattr(resp, 'user', None) or resp.get('data')
                                session = resp.get('session')
                                # Robustly extract id from dict-like or SDK user object
                                uid = None
                                if isinstance(user, dict):
                                    uid = user.get('id') or user.get('user', {}).get('id') if user.get('user') else user.get('id')
                                elif user is not None:
                                    # SDK object: try attribute access
                                    uid = getattr(user, 'id', None) or getattr(user, 'user', None) and getattr(user.user, 'id', None)

                                if uid:
                                    st.session_state.user_id = uid
                                    # Store tokens for RLS-backed operations
                                    access_token = None
                                    refresh_token = None
                                    if isinstance(session, dict):
                                        access_token = session.get('access_token')
                                        refresh_token = session.get('refresh_token')
                                    elif session is not None:
                                        access_token = getattr(session, 'access_token', None)
                                        refresh_token = getattr(session, 'refresh_token', None)

                                    st.session_state.supabase_access_token = access_token
                                    st.session_state.supabase_refresh_token = refresh_token

                                    # Propagate user context to the agent/service so all writes use user JWT.
                                    try:
                                        agent.service.set_user_context(uid, access_token=access_token, refresh_token=refresh_token)
                                        agent.knowledge_repo.load()
                                    except Exception:
                                        pass
                                    st.success("Signed in")
                                else:
                                    st.error("Sign in failed or user id not available")
                            except Exception as e:
                                st.error(f"Sign in error: {e}")
                with col2:
                    if st.button("Sign Up"):
                            try:
                                resp = sup.auth_sign_up(email, password)
                                user = resp.get('user') or getattr(resp, 'user', None) or resp.get('data')
                                session = resp.get('session')
                                uid = None
                                if isinstance(user, dict):
                                    uid = user.get('id') or user.get('user', {}).get('id') if user.get('user') else user.get('id')
                                elif user is not None:
                                    uid = getattr(user, 'id', None) or getattr(user, 'user', None) and getattr(user.user, 'id', None)

                                if uid:
                                    st.session_state.user_id = uid
                                    access_token = None
                                    refresh_token = None
                                    if isinstance(session, dict):
                                        access_token = session.get('access_token')
                                        refresh_token = session.get('refresh_token')
                                    elif session is not None:
                                        access_token = getattr(session, 'access_token', None)
                                        refresh_token = getattr(session, 'refresh_token', None)

                                    st.session_state.supabase_access_token = access_token
                                    st.session_state.supabase_refresh_token = refresh_token

                                    try:
                                        agent.service.set_user_context(uid, access_token=access_token, refresh_token=refresh_token)
                                        agent.knowledge_repo.load()
                                    except Exception:
                                        pass
                                    st.success("Signed up")
                                else:
                                    st.info("Check email for confirmation link if required")
                            except Exception as e:
                                st.error(f"Sign up error: {e}")
            else:
                st.markdown(f"Signed in: `{st.session_state.get('user_id')}`")
                if st.button("Sign Out"):
                    st.session_state.pop('user_id', None)
                    st.session_state.pop('supabase_access_token', None)
                    st.session_state.pop('supabase_refresh_token', None)
                    try:
                        agent.service.set_user_context(None)
                        agent.knowledge_repo.load()
                    except Exception:
                        pass
                    st.success("Signed out")

        st.markdown("---")
        st.header("📚 Knowledge Base")
        st.write(f"Lessons: {len(agent.knowledge_repo.all())}")

        st.markdown("---")
        st.info(f"**Model:** {config.MODEL_NAME}")
        st.info(f"**Device:** {agent.model_handler.device}")

        # Stop button for ongoing operations
        if st.session_state.operation_running:
            st.error(f"⚠️ {st.session_state.operation_type} in progress...")
            if st.button("⏹️ Stop Operation", type="secondary"):
                st.session_state.stop_requested = True
                st.rerun()

        st.markdown("---")

        if st.button("📖 View Topics"):
            # Only show topics owned by the signed-in user
            uid = st.session_state.get('user_id')
            if not uid:
                st.info("Sign in to view your topics")
            else:
                owned = [l for l in agent.knowledge_repo.all() if l.get('owner_id') and str(l.get('owner_id')) == str(uid)]
                if not owned:
                    st.info("You have no saved topics yet.")
                for l in owned:
                    st.markdown(f"**{l.get('topic')}** - {l.get('subject')}")
    
    # Tabs
    tab1, tab2, tab3 = st.tabs(["💬 Ask", "📝 Practice", "📊 Manage"])
    
    # Ask Question
    with tab1:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            text_query = st.text_area("❓ Question:", height=100)
        
        with col2:
            st.markdown("### 📤 Image Upload")
            uploaded_file = st.file_uploader(
                "Upload image (PNG, JPG, JPEG)",
                type=['png', 'jpg', 'jpeg'],
                help="Upload images for Qwen3-VL analysis - supports math, diagrams, and handwritten content"
            )

            if uploaded_file:
                image = Image.open(uploaded_file)

                # Validate image
                if ImageProcessor.validate_image(image):
                    st.image(image, use_container_width=True, caption="Uploaded Image")

                    # Image type selector for better processing
                    image_type = st.selectbox(
                        "📋 Image Content Type:",
                        ["General Text", "Math Equations", "Diagram/Chart", "Handwritten Notes"],
                        help="Select the type of content for optimized processing"
                    )

                    # Store image type in session state for processing
                    st.session_state.image_type = image_type

                    # Show processing hints based on type
                    hints = {
                        "General Text": "📄 Optimized for general document analysis and text understanding",
                        "Math Equations": "🔢 Enhanced mathematical symbol and equation recognition",
                        "Diagram/Chart": "📊 Advanced visual analysis for diagrams and data charts",
                        "Handwritten Notes": "✍️ Specialized recognition for handwritten content"
                    }
                    st.info(f"ℹ️ {hints[image_type]}")

                    # Resize if necessary
                    original_size = image.size
                    image = ImageProcessor.resize_image(image)
                    if image.size != original_size:
                        st.info(f"📏 Image resized from {original_size[0]}×{original_size[1]} to {image.size[0]}×{image.size[1]} for optimal processing")

                    # Show image info
                    st.caption(f"📏 Processed image size: {image.size[0]}×{image.size[1]} pixels")
                else:
                    st.error("❌ Please upload a valid image file")
        
        if st.button("🚀 Get Explanation", type="primary", disabled=st.session_state.operation_running):
            if not text_query and not uploaded_file:
                st.warning("Enter a question or upload an image!")
            elif st.session_state.operation_running:
                st.warning("Another operation is already running. Please wait or stop it first.")
            else:
                # Set operation status
                st.session_state.operation_running = True
                st.session_state.operation_type = "Generating Explanation"
                st.session_state.stop_requested = False

                try:
                    with st.spinner("Analyzing..."):
                        image = Image.open(uploaded_file) if uploaded_file else None
                        image_type = getattr(st.session_state, 'image_type', 'General Text')
                        relevant, query, _ = agent.process_query(text_query, image, image_type)

                        # Persist query + attachments (best-effort) when signed in.
                        try:
                            uid = st.session_state.get('user_id')
                            if uid:
                                image_bytes_list = [uploaded_file.getvalue()] if uploaded_file else None
                                content_types = [getattr(uploaded_file, 'type', None) or 'image/png'] if uploaded_file else None
                                st.session_state.last_query_id = agent.service.store_user_query(
                                    uid,
                                    query or text_query or '',
                                    image_bytes_list=image_bytes_list,
                                    content_types=content_types,
                                )
                        except Exception:
                            pass

                        if st.session_state.stop_requested:
                            st.warning("❌ Operation cancelled by user")
                            st.session_state.operation_running = False
                            st.session_state.operation_type = None
                            st.rerun()

                        if relevant is None:
                            st.warning("Please provide a question!")
                            st.session_state.operation_running = False
                            st.session_state.operation_type = None
                            st.stop()

                        st.success("✅ Found relevant material!")

                        with st.expander("📚 Relevant Lessons"):
                            for l in relevant:
                                st.markdown(f"**{l['topic']}** - {l['similarity']:.2%}\n\n{l['content']}")

                        with st.spinner("Generating..."):
                            explanation = agent.generate_explanation(query, relevant, image)
                            if st.session_state.stop_requested:
                                st.warning("❌ Explanation generation cancelled")
                            else:
                                st.markdown("### 💡 Explanation")
                                st.markdown(explanation)

                finally:
                    # Reset operation status
                    st.session_state.operation_running = False
                    st.session_state.operation_type = None
                    st.session_state.stop_requested = False
    
    # Practice
    with tab2:
        st.header("📝 Practice")
        
        # Only allow selecting topics that belong to the current user
        uid = st.session_state.get('user_id')
        available_topics = [l.get('topic') for l in agent.knowledge_repo.all() if l.get('owner_id') and str(l.get('owner_id')) == str(uid)] if uid else []
        topic = st.selectbox("Topic:", available_topics)
        
        if st.button("Generate Question", disabled=st.session_state.operation_running):
            if st.session_state.operation_running:
                st.warning("Another operation is already running. Please wait or stop it first.")
            else:
                # Set operation status
                st.session_state.operation_running = True
                st.session_state.operation_type = "Generating Question"
                st.session_state.stop_requested = False

                try:
                    with st.spinner("Creating..."):
                        question = agent.generate_practice_question(topic)
                        if st.session_state.stop_requested:
                            st.warning("❌ Question generation cancelled")
                        else:
                            st.session_state.practice_question = question
                            st.session_state.topic = topic
                finally:
                    # Reset operation status
                    st.session_state.operation_running = False
                    st.session_state.operation_type = None
                    st.session_state.stop_requested = False
        
        if 'practice_question' in st.session_state:
            st.info(st.session_state.practice_question)
            answer = st.text_area("Your Answer:", height=150)
            
            if st.button("Submit", disabled=st.session_state.operation_running):
                if st.session_state.operation_running:
                    st.warning("Another operation is already running. Please wait or stop it first.")
                elif answer:
                    # Set operation status
                    st.session_state.operation_running = True
                    st.session_state.operation_type = "Evaluating Answer"
                    st.session_state.stop_requested = False

                    try:
                        lesson = next((l.get('content') for l in agent.knowledge_repo.all()
                                     if l.get('topic') == st.session_state.topic), "")

                        with st.spinner("Evaluating..."):
                            feedback = agent.evaluate_answer(
                                st.session_state.practice_question, answer, lesson
                            )
                            if st.session_state.stop_requested:
                                st.warning("❌ Answer evaluation cancelled")
                            else:
                                st.success(feedback)
                    finally:
                        # Reset operation status
                        st.session_state.operation_running = False
                        st.session_state.operation_type = None
                        st.session_state.stop_requested = False
    
    # Manage
    with tab3:
        st.header("📊 Manage Knowledge")
        
        with st.form("add"):
            new_topic = st.text_input("Topic")
            new_content = st.text_area("Content")
            new_subject = st.text_input("Subject")
            new_level = st.selectbox("Level", ["Elementary", "Middle School", "High School", "College"])
            
            if st.form_submit_button("Add"):
                if not st.session_state.get('user_id'):
                    st.warning("You must be signed in to add a topic.")
                elif new_topic and new_content:
                    # Add via repository (persists to Supabase when configured)
                    added = agent.knowledge_repo.add(new_topic, new_content, new_subject, new_level, owner_id=st.session_state.get('user_id'))
                    if not added:
                        st.error("❌ Failed to add topic to Supabase. Check server logs for details.")
                    else:
                        # Refresh cache and UI
                        try:
                            agent.knowledge_repo.load()
                        except Exception:
                            pass
                        st.success("✅ Added!")
                        st.rerun()
        
        st.markdown("---")
        # Only display topics owned by the current user
        uid = st.session_state.get('user_id')
        if not uid:
            st.info("Sign in to view your saved topics")
        else:
            owned = [l for l in agent.knowledge_repo.all() if l.get('owner_id') and str(l.get('owner_id')) == str(uid)]
            for l in owned:
                lid = l.get('id')
                with st.expander(f"{l.get('topic')} - {l.get('subject')}"):
                    st.write(l.get('content'))
                    cols = st.columns([1, 1, 3])
                    # Delete button - set pending deletion in session state
                    with cols[0]:
                        if st.button("Delete", key=f"del_{lid}"):
                            st.session_state['delete_pending'] = str(lid)
                            st.session_state['delete_topic'] = l.get('topic')
                            safe_rerun()

                    with cols[1]:
                        if st.button("Make Public", key=f"pub_{lid}"):
                            try:
                                sup = agent.knowledge_repo._get_supabase()
                                if sup:
                                    sup.table_update('lessons', {'visibility': 'public'}, 'id', lid)
                                    agent.knowledge_repo.load()
                                    st.success("Topic made public")
                                else:
                                    st.warning("Supabase not configured")
                            except Exception:
                                st.error("Failed to update visibility")
                    with cols[2]:
                        st.write("")

            # Confirmation "popup" (session-state driven)
            if st.session_state.get('delete_pending'):
                pending_id = st.session_state.get('delete_pending')
                pending_topic = st.session_state.get('delete_topic', '')
                # Try to use modal if available
                modal = getattr(st, 'modal', None)
                if modal:
                    with st.modal("Confirm delete"):
                        st.warning(f"Are you sure you want to delete '**{pending_topic}**' ? This action cannot be undone.")
                        c1, c2 = st.columns(2)
                        if c1.button("Confirm Delete", key=f"confirm_delete_{pending_id}"):
                            success = agent.knowledge_repo.delete_lesson(pending_id)
                            if success:
                                st.success("Deleted topic")
                                # clear pending and refresh
                                st.session_state.pop('delete_pending', None)
                                st.session_state.pop('delete_topic', None)
                                agent.knowledge_repo.load()
                                safe_rerun()
                            else:
                                st.error("Failed to delete topic. Check server logs or permissions.")
                        if c2.button("Cancel", key=f"cancel_delete_{pending_id}"):
                            st.session_state.pop('delete_pending', None)
                            st.session_state.pop('delete_topic', None)
                            safe_rerun()
                else:
                    # Fallback inline confirmation
                    with st.container():
                        st.warning(f"Confirm deletion of '**{pending_topic}**' ? This action cannot be undone.")
                        c1, c2 = st.columns(2)
                        if c1.button("Confirm Delete", key=f"confirm_delete_{pending_id}"):
                            success = agent.knowledge_repo.delete_lesson(pending_id)
                            if success:
                                st.success("Deleted topic")
                                st.session_state.pop('delete_pending', None)
                                st.session_state.pop('delete_topic', None)
                                agent.knowledge_repo.load()
                                safe_rerun()
                            else:
                                st.error("Failed to delete topic. Check server logs or permissions.")
                        if c2.button("Cancel", key=f"cancel_delete_{pending_id}"):
                            st.session_state.pop('delete_pending', None)
                            st.session_state.pop('delete_topic', None)
                            safe_rerun()


if __name__ == "__main__":
    main()
