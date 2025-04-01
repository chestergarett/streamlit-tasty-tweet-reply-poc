import base64
import vertexai
from vertexai.generative_models import GenerativeModel, SafetySetting, Part,Image, HarmCategory, HarmBlockThreshold
from PIL import Image as PILImage
import streamlit as st
import io
import tempfile
import os
import json
import requests
from google.oauth2 import service_account

# Set page config to wide mode
st.set_page_config(layout="wide")

# Detect mobile devices
def is_mobile():
    try:
        import user_agents
        user_agent = st.get_user_agent()
        return user_agents.parse(user_agent).is_mobile
    except:
        # Fallback to viewport width detection
        return False

# Initialize session state for mobile view
if 'mobile_view' not in st.session_state:
    st.session_state.mobile_view = is_mobile()

# Custom CSS for responsive design
st.markdown("""
    <style>
    .stApp {
        max-width: 100%;
        padding: 1rem;
    }
    
    /* Center title */
    .title-container {
        text-align: center;
        padding: 1rem 0;
        margin-bottom: 2rem;
    }
    .title-container h1 {
        font-size: 2.5rem;
        font-weight: bold;
        color: #262730 !important;
    }
    
    /* Card styles with dark mode support */
    .header-card {
        background-color: #f0f2f6 !important;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .header-card h3 {
        color: #262730 !important;
        margin: 0;
    }
    
    .content-card {
        background-color: #ffffff !important;
        padding: 1.5rem;
        border-radius: 0.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.12);
        color: #262730 !important;
    }
    
    .content-card .description {
        font-weight: bold;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid #e0e0e0;
    }
    
    .content-card .reply {
        padding: 0.5rem 0;
        margin: 0.25rem 0;
    }
    
    /* Responsive container */
    @media (max-width: 640px) {
        .main > div {
            padding: 0;
        }
        .stTextArea > div > textarea {
            font-size: 16px; /* Prevent zoom on mobile */
        }
    }
    
    /* Custom container for results */
    .results-container {
        display: flex;
        flex-direction: column;
        gap: 1rem;
        padding: 1rem;
    }
    
    @media (min-width: 641px) {
        .results-container {
            flex-direction: row;
            flex-wrap: wrap;
        }
    }

    /* Dark mode overrides */
    @media (prefers-color-scheme: dark) {
        .title-container h1 {
            color: #ffffff !important;
        }
        .header-card {
            background-color: #2e2e2e !important;
        }
        .header-card h3 {
            color: #ffffff !important;
        }
        .content-card {
            background-color: #1e1e1e !important;
            color: #ffffff !important;
        }
        
        .content-card .description {
            border-bottom-color: #404040;
        }
    }
    </style>
""", unsafe_allow_html=True)

# Load service account credentials
with open('authentication_creds.json') as f:
    credentials_dict = json.load(f)

# Create credentials object
credentials = service_account.Credentials.from_service_account_info(credentials_dict)

# Generation config for Vertex AI
generation_config = {
    "max_output_tokens": 8192,
    "temperature": 1,
    "top_p": 0.95,
}

# Initialize Vertex AI with credentials
vertexai.init(
    project="groovy-legacy-438407-u5",
    location="us-central1",
    credentials=credentials
)

# Safety settings for Vertex AI
safety_settings = {
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.OFF,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.OFF,
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.OFF,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.OFF,
}

# System instruction
system_instruction = '''
    You are posting a picture on Twitter and you need to generate a flirty caption for that picture. Here are some examples:
    caption 1: thick is the new sexy🤭,
    caption 2: more than you can handle🤭,
    caption 3: can I sit next to you?🤭,
    caption 4: have you seen mine?🤭,
    caption 5: don't just stare at me🤭,
    caption 6: who wants a squeeze? 🤭,
    caption 7: wanna hit it from behind?,
    caption 8: my laundry vid got leaked
'''

# Streamlit app
st.markdown('<div class="title-container"><h1>Bump Gen AI</h1></div>', unsafe_allow_html=True)

# Create a container with custom width for the form
form_container = st.container()
with form_container:
    # Responsive columns - adjust ratios for different screen sizes
    if st.session_state.get('mobile_view', False):
        form_col = st.columns([1])[0]  # Full width on mobile
    else:
        _, form_col, _ = st.columns([1, 2, 1])  # Centered on desktop
    
    with form_col:
        st.text("Enter image URLs (one per line or separated by commas) and provide a prompt for reply generation")

        # Single textbox for multiple URLs
        urls_input = st.text_area("Image URLs", 
                                help="Enter multiple image URLs (one per line or separated by commas). Maximum 8 images allowed.")

        # Text input for prompt
        user_prompt = st.text_area("Enter your prompt here", "")
        
        # Submit button
        generate_button = st.button("Generate Replies")

# Process URLs
urls = []
if urls_input:
    # Split by both newlines and commas, then clean up
    raw_urls = [url.strip() for url in urls_input.replace(',', '\n').split('\n')]
    urls = [url for url in raw_urls if url]  # Remove empty strings

# Limit to 8 URLs
if len(urls) > 8:
    st.warning("Maximum 8 images allowed. Only the first 8 will be processed.")
    urls = urls[:8]

# Placeholder for image inputs
image_inputs = []
temp_file_paths = []
images = []  # Store PIL images for reuse

if urls:
    # Process images without preview
    for idx, url in enumerate(urls):
        try:
            # Download image from URL
            response = requests.get(url)
            if response.status_code == 200:
                # Create temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
                    temp_file.write(response.content)
                    temp_file_path = temp_file.name
                    temp_file_paths.append(temp_file_path)
                    
                    # Process image without displaying
                    image = PILImage.open(io.BytesIO(response.content))
                    images.append(image.copy())  # Store a copy of the image
                    
                    # Convert image to base64
                    if image.mode in ("RGBA", "LA"):
                        image = image.convert("RGB")
                    image.thumbnail((300, 300))  # Resize to reduce size
                    buffer = io.BytesIO()
                    image.save(buffer, format="JPEG", quality=50)  # Compress and save as JPEG
                    buffer.seek(0)
                    encoded_image = base64.b64encode(buffer.read()).decode("utf-8")
                    image_inputs.append(Part.from_image(Image.load_from_file(temp_file_path)))
            else:
                st.error(f"Failed to load image from URL {idx + 1}")
        except Exception as e:
            st.error(f"Error processing image {idx + 1}: {str(e)}")

# Submit button
if generate_button:
    if user_prompt or image_inputs:  # Allow generation with either prompt or images
        try:
            # Initialize Vertex AI generative model
            model = GenerativeModel(
                "gemini-1.5-flash-002",
            )
            
            # Process images in groups of 3 (or 1 on mobile)
            group_size = 1 if st.session_state.get('mobile_view', False) else 3  # Changed back to 3
            for i in range(0, len(image_inputs), group_size):
                # Create columns for displaying results
                result_cols = st.columns(group_size)
                
                # Process images in the current group
                for j in range(group_size):
                    if i + j < len(image_inputs):
                        with result_cols[j]:
                            idx = i + j
                            st.markdown(
                                f"<div class='header-card'><h3>Generated Reply for Image {idx + 1}</h3></div>",
                                unsafe_allow_html=True
                            )
                            
                            # Display the image with responsive width
                            st.image(images[idx], use_container_width=True)
                            
                            chat = model.start_chat()
                            
                            # Prepare inputs
                            inputs = []
                            inputs.append("""Analyze the image and generate replies in the following format:
1. First line should be a brief description of the image
2. Then generate exactly 10 witty, flirty, and suggestive one-liner captions
3. Each caption should include at least one emoji
4. Format the output exactly like this:
Description: [brief image description]
1️⃣ [first caption]
2️⃣ [second caption]
3️⃣ [third caption]
4️⃣ [fourth caption]
5️⃣ [fifth caption]
6️⃣ [sixth caption]
7️⃣ [seventh caption]
8️⃣ [eighth caption]
9️⃣ [ninth caption]
🔟 [tenth caption]""")
                            inputs.append(image_inputs[idx])
                            if user_prompt:
                                inputs.append(user_prompt)

                            # Send the inputs to the model
                            response = chat.send_message(
                                inputs,
                                generation_config=generation_config,
                                safety_settings=safety_settings,
                            )

                            # Format the response with proper HTML structure
                            response_lines = response.text.strip().split('\n')
                            formatted_html = []
                            
                            for line in response_lines:
                                line = line.strip()
                                if line.startswith('Description:'):
                                    formatted_html.append(f'<div class="description">{line}</div>')
                                elif any(line.startswith(str(i)) for i in range(1, 10)) or line.startswith('10') or line.startswith('🔟'):
                                    formatted_html.append(f'<div class="reply">{line}</div>')
                            
                            formatted_response = '\n'.join(formatted_html)
                            
                            # Display the formatted response
                            st.markdown(
                                f"<div class='content-card'>{formatted_response}</div>",
                                unsafe_allow_html=True
                            )
                            st.markdown("<hr style='margin: 2rem 0;'>", unsafe_allow_html=True)

            # Clean up temporary files
            for temp_file_path in temp_file_paths:
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
                    
        except Exception as e:
            st.error(f"An error occurred: {e}")
    else:
        st.warning("Please enter a prompt or provide image URLs before generating replies.")