"""
OpenCV Quality Check Service
Step 1 in the pipeline: Image quality validation
"""

import cv2
import numpy as np
from PIL import Image
from typing import Dict, Tuple


class QualityCheckService:
    def __init__(self):
        """Initialize quality check thresholds"""
        self.min_resolution = 100  # minimum width/height
        self.max_resolution = 10000  # maximum width/height
        self.min_aspect_ratio = 0.2  # 1:5
        self.max_aspect_ratio = 5.0  # 5:1
        self.blur_threshold = 100.0  # Laplacian variance threshold
        self.min_filesize = 1024  # 1KB minimum
        
        print("Quality Check Service initialized")
    
    def check_image(self, image: Image.Image, file_size: int = None) -> Dict:
        """
        Comprehensive image quality check
        
        Returns:
            Dict with pass/fail status and reasons
        """
        checks = {
            "resolution": self._check_resolution(image),
            "aspect_ratio": self._check_aspect_ratio(image),
            "blur": self._check_blur(image),
            "corrupted": self._check_corrupted(image),
            "screenshot_ui": self._check_screenshot_ui(image),
        }
        
        # Determine overall pass/fail
        failed_checks = [name for name, result in checks.items() if not result["passed"]]
        passed = len(failed_checks) == 0
        
        return {
            "passed": passed,
            "checks": checks,
            "failed_checks": failed_checks,
            "action": "PASS" if passed else "BLOCK",
            "reason": ", ".join(failed_checks) if failed_checks else "All quality checks passed"
        }
    
    def _check_resolution(self, image: Image.Image) -> Dict:
        """Check if image resolution is within acceptable range"""
        width, height = image.size
        
        # Check minimum resolution
        if width < self.min_resolution or height < self.min_resolution:
            return {
                "passed": False,
                "reason": f"Resolution too low: {width}x{height}",
                "details": {"width": width, "height": height}
            }
        
        # Check maximum resolution
        if width > self.max_resolution or height > self.max_resolution:
            return {
                "passed": False,
                "reason": f"Resolution too high: {width}x{height}",
                "details": {"width": width, "height": height}
            }
        
        return {
            "passed": True,
            "reason": "Resolution acceptable",
            "details": {"width": width, "height": height}
        }
    
    def _check_aspect_ratio(self, image: Image.Image) -> Dict:
        """Check if aspect ratio is reasonable"""
        width, height = image.size
        aspect_ratio = width / height if height > 0 else 0
        
        if aspect_ratio < self.min_aspect_ratio or aspect_ratio > self.max_aspect_ratio:
            return {
                "passed": False,
                "reason": f"Unusual aspect ratio: {aspect_ratio:.2f}",
                "details": {"aspect_ratio": aspect_ratio}
            }
        
        return {
            "passed": True,
            "reason": "Aspect ratio acceptable",
            "details": {"aspect_ratio": aspect_ratio}
        }
    
    def _check_blur(self, image: Image.Image) -> Dict:
        """Check if image is too blurry using Laplacian variance"""
        # Convert to grayscale
        img_array = np.array(image.convert('L'))
        
        # Calculate Laplacian variance
        laplacian_var = cv2.Laplacian(img_array, cv2.CV_64F).var()
        
        if laplacian_var < self.blur_threshold:
            return {
                "passed": False,
                "reason": f"Image too blurry: {laplacian_var:.2f}",
                "details": {"blur_score": laplacian_var}
            }
        
        return {
            "passed": True,
            "reason": "Image sharpness acceptable",
            "details": {"blur_score": laplacian_var}
        }
    
    def _check_corrupted(self, image: Image.Image) -> Dict:
        """Check if image appears corrupted"""
        try:
            # Try to get pixel data
            img_array = np.array(image)
            
            # Check for valid data
            if img_array.size == 0:
                return {
                    "passed": False,
                    "reason": "Image has no data",
                    "details": {}
                }
            
            # Check for unusual patterns (all same color, etc.)
            if len(img_array.shape) >= 2:
                std_dev = np.std(img_array)
                if std_dev < 1.0:  # Nearly uniform color
                    return {
                        "passed": False,
                        "reason": "Image appears corrupted (uniform color)",
                        "details": {"std_dev": std_dev}
                    }
            
            return {
                "passed": True,
                "reason": "Image not corrupted",
                "details": {}
            }
        
        except Exception as e:
            return {
                "passed": False,
                "reason": f"Image corrupted: {str(e)}",
                "details": {"error": str(e)}
            }
    
    def _check_screenshot_ui(self, image: Image.Image) -> Dict:
        """Check if image is likely a screenshot or UI element"""
        img_array = np.array(image)
        
        # Convert to grayscale
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array
        
        # Detect edges
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / edges.size
        
        # High edge density might indicate UI elements/screenshots
        # This is a simple heuristic - can be refined
        if edge_density > 0.15:  # More than 15% edges
            # Additional check: look for rectangular regions
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            rectangular_contours = 0
            for contour in contours:
                perimeter = cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
                if len(approx) == 4:  # Rectangle
                    rectangular_contours += 1
            
            if rectangular_contours > 10:  # Many rectangles suggest UI
                return {
                    "passed": False,
                    "reason": "Likely screenshot or UI element",
                    "details": {
                        "edge_density": edge_density,
                        "rectangles": rectangular_contours
                    }
                }
        
        return {
            "passed": True,
            "reason": "Not a screenshot",
            "details": {"edge_density": edge_density}
        }
    
    def _check_watermark(self, img_array: np.ndarray) -> bool:
        """
        Check for watermarks using edge detection and text patterns
        Watermarks often appear as semi-transparent text or logos
        """
        try:
            # Convert to grayscale
            if len(img_array.shape) == 3:
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_array
            
            # Apply edge detection
            edges = cv2.Canny(gray, 50, 150)
            
            # Check for diagonal patterns (common in watermarks)
            height, width = edges.shape
            
            # Sample regions (corners and center) where watermarks typically appear
            regions = [
                edges[0:height//4, 0:width//4],  # Top-left
                edges[0:height//4, 3*width//4:width],  # Top-right
                edges[3*height//4:height, 0:width//4],  # Bottom-left
                edges[3*height//4:height, 3*width//4:width],  # Bottom-right
                edges[height//3:2*height//3, width//3:2*width//3]  # Center
            ]
            
            watermark_detected = False
            for region in regions:
                if region.size == 0:
                    continue
                    
                # Calculate edge density
                edge_density = np.sum(region > 0) / region.size
                
                # High edge density in specific regions suggests watermark
                if edge_density > 0.15:
                    watermark_detected = True
                    break
            
            # Check for repeating patterns (tiled watermarks)
            if not watermark_detected:
                # Check for semi-transparent overlays by analyzing pixel intensity variance
                std_dev = np.std(gray)
                mean_intensity = np.mean(gray)
                
                # Watermarks often create subtle but consistent patterns
                # Check if there's unusual uniformity suggesting overlay
                if std_dev < 30 and mean_intensity > 200:
                    # Very uniform bright image might have watermark
                    watermark_detected = True
            
            # Return True if NO watermark detected (passed check)
            return not watermark_detected
            
        except Exception as e:
            print(f"Warning: Watermark check failed - {e}")
            return True  # If check fails, assume no watermark
