"""Streamlit-friendly image processing helpers (UI layer)."""

import numpy as np
import streamlit as st
from PIL import Image


class ImageProcessor:
    @staticmethod
    def validate_image(image):
        try:
            img_array = np.array(image)
            height, width = img_array.shape[:2]

            min_pixels = 224 * 224
            if height * width < min_pixels:
                st.warning(f"⚠️ Image too small ({width}x{height}). Minimum: {int(min_pixels**0.5)}x{int(min_pixels**0.5)} pixels")
                return False

            max_pixels = 1280 * 1280
            if height * width > max_pixels:
                st.info(f"📏 Large image detected ({width}x{height}). Will be resized for optimal processing.")

            return True
        except Exception as e:
            st.error(f"❌ Invalid image format: {e}")
            return False

    @staticmethod
    def resize_image(image, max_pixels=1280*1280):
        img_array = np.array(image)
        height, width = img_array.shape[:2]

        if height * width <= max_pixels:
            return image

        aspect_ratio = width / height
        new_height = int((max_pixels / aspect_ratio) ** 0.5)
        new_width = int(new_height * aspect_ratio)

        new_height = max(new_height, 224)
        new_width = max(new_width, 224)

        resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        return resized
