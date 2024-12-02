import streamlit as st
from streamlit_drawable_canvas import st_canvas
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import json
import io
from datetime import datetime
import os

def initialize_session_state():
    """Initialize session state variables"""
    if "annotations" not in st.session_state:
        st.session_state["annotations"] = []
    if "current_tool" not in st.session_state:
        st.session_state["current_tool"] = "rect"
    if "annotation_history" not in st.session_state:
        st.session_state["annotation_history"] = []
    if "is_authenticated" not in st.session_state:
        st.session_state["is_authenticated"] = False

def authenticate_user():
    """Handle user authentication"""
    st.title("🏥 Alyse AI Prescription Annotation Tool")
    
    if not st.session_state["is_authenticated"]:
        with st.form("login_form"):
            st.write("Please enter your credentials to access the tool.")
            username = st.text_input("Username:")
            password = st.text_input("Password:", type="password")
            submit = st.form_submit_button("Login")
            
            if submit:
                if username == "alyse" and password == "pharmacie":
                    st.session_state["is_authenticated"] = True
                    st.success("✅ Access granted! You can now use the application.")
                    st.rerun()
                else:
                    st.error("❌ Invalid credentials. Please try again.")
        return False
    return True

def create_sidebar_controls():
    """Create sidebar controls for annotation settings"""
    st.sidebar.header("📋 Annotation Controls")
    
    # Tool selection
    tool_options = {
        "rect": "Rectangle Box",
        "line": "Line",
        "circle": "Circle",
        "freedraw": "Free Draw"
    }
    st.session_state["current_tool"] = st.sidebar.radio(
        "Select Drawing Tool:",
        options=list(tool_options.keys()),
        format_func=lambda x: tool_options[x]
    )
    
    # Color selection
    stroke_color = st.sidebar.color_picker("Stroke Color:", "#0000FF")
    stroke_width = st.sidebar.slider("Stroke Width:", 1, 10, 2)
    
    # Annotation categories
    annotation_category = st.sidebar.selectbox(
        "Annotation Category:",
        ["Medication Name", "Dosage", "Frequency", "Duration", "Patient Info", "Doctor Info", "Other"]
    )
    
    return stroke_color, stroke_width, annotation_category

def preprocess_image(image):
    """Resize image if too large for Streamlit Cloud"""
    max_size = (800, 800)  # Maximum dimensions
    
    # Calculate aspect ratio
    width_ratio = max_size[0] / image.size[0]
    height_ratio = max_size[1] / image.size[1]
    resize_ratio = min(width_ratio, height_ratio)
    
    # Only resize if image is too large
    if resize_ratio < 1:
        new_size = (
            int(image.size[0] * resize_ratio),
            int(image.size[1] * resize_ratio)
        )
        return image.resize(new_size, Image.Resampling.LANCZOS)
    return image

def handle_canvas_drawing(image, stroke_color, stroke_width, category):
    """Handle canvas drawing with preprocessed image"""
    processed_image = preprocess_image(image)
    
    canvas_result = st_canvas(
        fill_color="rgba(0, 0, 0, 0)",
        stroke_width=stroke_width,
        stroke_color=stroke_color,
        background_image=processed_image,
        update_streamlit=True,
        width=processed_image.size[0],
        height=processed_image.size[1],
        drawing_mode=st.session_state["current_tool"],
        display_toolbar=True,
        key="canvas",
    )
    
    if canvas_result.json_data:
        objects = canvas_result.json_data.get("objects", [])
        for obj in objects:
            if obj not in [ann.get("object_data") for ann in st.session_state["annotations"]]:
                new_annotation = {
                    "object_data": obj,
                    "category": category,
                    "text": "",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                st.session_state["annotations"].append(new_annotation)
                st.session_state["annotation_history"].append(new_annotation)


def display_annotation_list():
    """Display and manage list of annotations"""
    st.sidebar.subheader("📝 Current Annotations")
    
    for i, annotation in enumerate(st.session_state["annotations"]):
        with st.sidebar.expander(f"Annotation {i+1} - {annotation['category']}"):
            # Update annotation text
            new_text = st.text_area(
                "Description:",
                annotation["text"],
                key=f"text_input_{i}"
            )
            st.session_state["annotations"][i]["text"] = new_text
            
            # Display annotation details
            st.write(f"Created: {annotation['timestamp']}")
            
            # Delete individual annotation
            if st.button("Delete", key=f"delete_{i}"):
                st.session_state["annotations"].pop(i)
                st.rerun()
def save_annotations(image, uploaded_file):
    """Handle saving and downloading annotations"""
    st.sidebar.subheader("💾 Save & Export")
    
    if st.sidebar.button("Save and Download"):
        # Create annotated image
        annotated_image = image.copy()
        draw = ImageDraw.Draw(annotated_image)
        
        # Draw annotations
        for annotation in st.session_state["annotations"]:
            obj = annotation["object_data"]
            if obj["type"] == "rect":
                draw.rectangle(
                    [obj["left"], obj["top"], 
                     obj["left"] + obj["width"], 
                     obj["top"] + obj["height"]],
                    outline=obj["stroke"],
                    width=int(obj["strokeWidth"])
                )
                # Add text label
                draw.text(
                    (obj["left"], obj["top"] - 15),
                    f"{annotation['category']}: {annotation['text']}",
                    fill=obj["stroke"]
                )
        
        # Save files
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save annotated image
        img_buffer = io.BytesIO()
        annotated_image.save(img_buffer, format="JPEG", quality=95)
        img_buffer.seek(0)
        
        # Save annotations JSON
        annotations_data = {
            "image_id": uploaded_file.name,
            "timestamp": timestamp,
            "annotations": [
                {
                    "category": ann["category"],
                    "text": ann["text"],
                    "timestamp": ann["timestamp"],
                    "object_data": ann["object_data"]
                }
                for ann in st.session_state["annotations"]
            ]
        }
        
        # Convert JSON to string first, then to bytes
        json_str = json.dumps(annotations_data, indent=2)
        json_bytes = json_str.encode('utf-8')
        json_buffer = io.BytesIO(json_bytes)
        
        # Download buttons
        col1, col2 = st.sidebar.columns(2)
        with col1:
            st.download_button(
                "📷 Download Image",
                data=img_buffer,
                file_name=f"annotated_{timestamp}.jpg",
                mime="image/jpeg"
            )
        with col2:
            st.download_button(
                "📄 Download JSON",
                data=json_buffer,
                file_name=f"annotations_{timestamp}.json",
                mime="application/json"
            )
        
        st.sidebar.success("✅ Files saved successfully!")
def main():
    """Main application logic"""
    initialize_session_state()
    
    if not authenticate_user():
        return
    
    # File upload
    uploaded_file = st.file_uploader(
        "📤 Upload Prescription Image",
        type=["jpg", "jpeg", "png"],
        help="Upload a clear image of the prescription to annotate"
    )
    
    if uploaded_file:
        # Load and display image
        image = Image.open(uploaded_file).convert("RGB")
        
        # Create two columns for layout
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Get annotation settings
            stroke_color, stroke_width, category = create_sidebar_controls()
            
            # Handle canvas drawing
            handle_canvas_drawing(image, stroke_color, stroke_width, category)
        
        with col2:
            # Undo/Redo buttons
            col_undo, col_redo, col_clear = st.columns(3)
            with col_undo:
                if st.button("↩️ Undo") and st.session_state["annotations"]:
                    last_annotation = st.session_state["annotations"].pop()
                    st.session_state["annotation_history"].append(last_annotation)
            
            with col_redo:
                if st.button("↪️ Redo") and st.session_state["annotation_history"]:
                    st.session_state["annotations"].append(
                        st.session_state["annotation_history"].pop()
                    )
            
            with col_clear:
                if st.button("🗑️ Clear All"):
                    st.session_state["annotations"] = []
                    st.session_state["annotation_history"] = []
        
        # Display annotation list
        display_annotation_list()
        
        # Save and download options
        save_annotations(image, uploaded_file)
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center'>
            <p><strong>Alyse AI Prescription Annotation Tool v2.0</strong></p>
            <p>Created by: Jad Tounsi El Azzoiani and Amine Tahiri</p>
            <p>Last Updated: November 2024</p>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    st.set_page_config(
        page_title="Alyse AI Prescription Annotator",
        page_icon="🏥",
        layout="wide"
    )
    main()
