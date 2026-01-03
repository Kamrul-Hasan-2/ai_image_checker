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
    
    def preprocess_image(self, image: Image.Image, enhance: bool = True) -> Image.Image:
        """
        Preprocess image for better detection
        - Contrast enhancement
        - Sharpening
        - Noise reduction
        """
        if not enhance:
            return image
        
        img_array = np.array(image)
        
        # Convert to LAB color space for better contrast adjustment
        if len(img_array.shape) == 3:
            lab = cv2.cvtColor(img_array, cv2.COLOR_RGB2LAB)
            l, a, b = cv2.split(lab)
            
            # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) to L channel
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l_enhanced = clahe.apply(l)
            
            # Merge channels back
            lab_enhanced = cv2.merge([l_enhanced, a, b])
            enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2RGB)
        else:
            # Grayscale image
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(img_array)
        
        # Sharpen the image
        kernel = np.array([[-1, -1, -1],
                          [-1,  9, -1],
                          [-1, -1, -1]])
        sharpened = cv2.filter2D(enhanced, -1, kernel)
        
        # Denoise slightly (preserve edges)
        if len(sharpened.shape) == 3:
            denoised = cv2.fastNlMeansDenoisingColored(sharpened, None, 10, 10, 7, 21)
        else:
            denoised = cv2.fastNlMeansDenoising(sharpened, None, 10, 7, 21)
        
        return Image.fromarray(denoised)
    
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
            "screenshot_ui": self._check_screenshot_ui(image)
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
        """Check if image is too blurry using multiple algorithms"""
        # Convert to grayscale
        img_array = np.array(image.convert('L'))
        
        # Method 1: Laplacian variance (edge detection)
        laplacian_var = cv2.Laplacian(img_array, cv2.CV_64F).var()
        
        # Method 2: Tenengrad (gradient magnitude)
        gx = cv2.Sobel(img_array, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(img_array, cv2.CV_64F, 0, 1, ksize=3)
        tenengrad_score = np.mean(gx**2 + gy**2)
        
        # Method 3: FFT-based frequency analysis
        fft = np.fft.fft2(img_array)
        fft_shift = np.fft.fftshift(fft)
        magnitude_spectrum = np.abs(fft_shift)
        
        # High frequency content indicates sharp image
        h, w = magnitude_spectrum.shape
        center_y, center_x = h // 2, w // 2
        radius = min(h, w) // 4
        
        # Create mask for high frequencies (outer region)
        y, x = np.ogrid[:h, :w]
        mask = ((x - center_x)**2 + (y - center_y)**2) > radius**2
        high_freq_energy = np.mean(magnitude_spectrum[mask])
        
        # Method 4: Edge density
        edges = cv2.Canny(img_array, 50, 150)
        edge_density = np.sum(edges > 0) / edges.size
        
        # Combined scoring (weighted average)
        # Normalize scores
        laplacian_normalized = min(laplacian_var / 500.0, 1.0)  # 500+ is very sharp
        tenengrad_normalized = min(tenengrad_score / 1000.0, 1.0)  # 1000+ is very sharp
        fft_normalized = min(high_freq_energy / 50.0, 1.0)  # Normalize FFT
        edge_normalized = min(edge_density / 0.15, 1.0)  # 15%+ edges is sharp
        
        # Weighted combined score (0-100)
        combined_score = (
            laplacian_normalized * 35 +
            tenengrad_normalized * 30 +
            fft_normalized * 20 +
            edge_normalized * 15
        ) * 100
        
        # Thresholds:
        # < 30: Very blurry (reject)
        # 30-45: Slightly blurry (borderline)
        # 45+: Acceptable
        is_blurry = combined_score < 30
        is_borderline = 30 <= combined_score < 45
        
        details = {
            "combined_score": combined_score,
            "laplacian_var": laplacian_var,
            "tenengrad_score": tenengrad_score,
            "high_freq_energy": high_freq_energy,
            "edge_density": edge_density,
            "quality_grade": "poor" if is_blurry else "borderline" if is_borderline else "good"
        }
        
        if is_blurry:
            return {
                "passed": False,
                "reason": f"Image too blurry (score: {combined_score:.1f}/100)",
                "details": details
            }
        
        return {
            "passed": True,
            "reason": f"Image sharpness acceptable (score: {combined_score:.1f}/100)",
            "details": details
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
    
    def detect_watermark(self, img_array: np.ndarray) -> Dict:
        """
        Detect 3rd party website watermarks (bikroy, daraz, etc.)
        Does NOT detect product names or brand logos
        """
        try:
            # Convert to grayscale
            if len(img_array.shape) == 3:
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_array
            
            height, width = gray.shape
            
            # Apply edge detection
            edges = cv2.Canny(gray, 50, 150)
            
            # Check ONLY corners where website watermarks typically appear
            # Exclude center region (where product logos usually are)
            corner_regions = {
                'top_left': edges[0:height//5, 0:width//5],
                'top_right': edges[0:height//5, 4*width//5:width],
                'bottom_left': edges[4*height//5:height, 0:width//5],
                'bottom_right': edges[4*height//5:height, 4*width//5:width]
            }
            
            watermark_detected = False
            watermark_location = None
            max_density = 0
            
            for location, region in corner_regions.items():
                if region.size == 0:
                    continue
                
                # Calculate edge density
                edge_density = np.sum(region > 0) / region.size
                
                # Website watermarks have higher edge density (0.12-0.30)
                # This filters out simple product names
                if edge_density > 0.12 and edge_density < 0.30:
                    # Check for URL-like patterns (dots, multiple words)
                    horizontal_edges = np.sum(region, axis=0)
                    vertical_edges = np.sum(region, axis=1)
                    
                    # Website watermarks often have more complex patterns
                    if np.max(horizontal_edges) > region.shape[0] * 15 and np.std(horizontal_edges) > 5:
                        watermark_detected = True
                        if edge_density > max_density:
                            max_density = edge_density
                            watermark_location = location
            
            # Additional check: Look for semi-transparent overlays ONLY in corners
            if not watermark_detected:
                corner_regions_bright = [
                    gray[0:height//5, 0:width//5],
                    gray[0:height//5, 4*width//5:width],
                    gray[4*height//5:height, 0:width//5],
                    gray[4*height//5:height, 4*width//5:width]
                ]
                
                for region in corner_regions_bright:
                    if region.size == 0:
                        continue
                    std_dev = np.std(region)
                    mean_val = np.mean(region)
                    
                    # Very specific for semi-transparent website overlays
                    # Low variance + high brightness + small region = watermark
                    if std_dev < 25 and mean_val > 200 and region.size < (height * width) / 20:
                        watermark_detected = True
                        break
            
            return {
                "has_watermark": watermark_detected,
                "location": watermark_location,
                "confidence": max_density
            }
            
        except Exception as e:
            print(f"Warning: Watermark detection failed - {e}")
            return {
                "has_watermark": False,
                "location": None,
                "confidence": 0
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
