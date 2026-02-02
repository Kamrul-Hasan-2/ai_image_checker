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
        self.min_resolution = 100  # minimum width/height (allows 400x400 and up)
        self.max_resolution = 10000  # maximum width/height
        self.min_aspect_ratio = 0.2  # 1:5
        self.max_aspect_ratio = 5.0  # 5:1
        self.blur_threshold = 70.0  # Laplacian variance threshold (balanced)
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
        Comprehensive image quality check with confidence scores
        
        Returns:
            Dict with pass/fail status, confidence scores, and reasons
        """
        checks = {
            "resolution": self._check_resolution(image),
            "aspect_ratio": self._check_aspect_ratio(image),
            "blur": self._check_blur(image),
            "corrupted": self._check_corrupted(image),
            "screenshot_ui": self._check_screenshot_ui(image)
        }
        
        # Extract confidence scores (0.0 to 1.0)
        screenshot_confidence = checks["screenshot_ui"].get("confidence", 0.0)
        blur_confidence = checks["blur"].get("confidence", 0.0)
        
        # Hard rule: OpenCV screenshot detection is FINAL
        opencv_block = screenshot_confidence > 0.7
        
        # Determine overall pass/fail
        failed_checks = [name for name, result in checks.items() if not result["passed"]]
        passed = len(failed_checks) == 0 and not opencv_block
        
        return {
            "passed": passed,
            "checks": checks,
            "failed_checks": failed_checks,
            "action": "BLOCK" if opencv_block else ("PASS" if passed else "BLOCK"),
            "reason": "Screenshot detected by OpenCV" if opencv_block else (", ".join(failed_checks) if failed_checks else "All quality checks passed"),
            "opencv_risk": screenshot_confidence * 0.7 + blur_confidence * 0.3,
            "screenshot_confidence": screenshot_confidence,
            "blur_confidence": blur_confidence
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
        """Check if image is too blurry or noisy using ADVANCED algorithms with feature engineering"""
        # Convert to grayscale
        img_array = np.array(image.convert('L'))
        
        # Method 1: Laplacian variance (edge detection) - ENHANCED
        laplacian = cv2.Laplacian(img_array, cv2.CV_64F)
        laplacian_var = laplacian.var()
        laplacian_mean = np.abs(laplacian).mean()
        
        # Method 2: Tenengrad (gradient magnitude) - ENHANCED
        gx = cv2.Sobel(img_array, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(img_array, cv2.CV_64F, 0, 1, ksize=3)
        gradient_magnitude = np.sqrt(gx**2 + gy**2)
        tenengrad_score = np.mean(gradient_magnitude**2)
        gradient_std = np.std(gradient_magnitude)
        
        # Method 3: FFT-based frequency analysis - ENHANCED
        fft = np.fft.fft2(img_array)
        fft_shift = np.fft.fftshift(fft)
        magnitude_spectrum = np.abs(fft_shift)
        
        # Analyze high frequency content (sharp images have more)
        h, w = magnitude_spectrum.shape
        center_y, center_x = h // 2, w // 2
        radius = min(h, w) // 4
        
        # Create mask for high frequencies (outer region)
        y, x = np.ogrid[:h, :w]
        mask_high = ((x - center_x)**2 + (y - center_y)**2) > radius**2
        mask_mid = (((x - center_x)**2 + (y - center_y)**2) > (radius//2)**2) & ~mask_high
        
        high_freq_energy = np.mean(magnitude_spectrum[mask_high])
        mid_freq_energy = np.mean(magnitude_spectrum[mask_mid])
        freq_ratio = high_freq_energy / (mid_freq_energy + 1e-10)  # Sharp images have good ratio
        
        # Method 4: Edge density and quality - ENHANCED WITH PRODUCT PHOTO AWARENESS
        edges = cv2.Canny(img_array, 50, 150)
        edge_density = np.sum(edges > 0) / edges.size
        
        # Strong edges detection (blur reduces edge strength)
        strong_edges = cv2.Canny(img_array, 100, 200)
        strong_edge_density = np.sum(strong_edges > 0) / strong_edges.size
        edge_strength_ratio = strong_edge_density / (edge_density + 1e-10)
        
        # PRODUCT PHOTO DETECTION: Check if edges are concentrated in center
        # Product photos often have clean backgrounds with detail in center
        h, w = img_array.shape
        center_y, center_w = h // 2, w // 2
        
        # Create center mask (50% of image in center)
        y_start, y_end = h // 4, 3 * h // 4
        x_start, x_end = w // 4, 3 * w // 4
        center_edges = edges[y_start:y_end, x_start:x_end]
        border_edges_top = edges[:h//4, :]
        border_edges_bottom = edges[3*h//4:, :]
        border_edges_left = edges[:, :w//4]
        border_edges_right = edges[:, 3*w//4:]
        
        center_edge_density = np.sum(center_edges > 0) / center_edges.size if center_edges.size > 0 else 0
        border_edge_density = (
            np.sum(border_edges_top > 0) + np.sum(border_edges_bottom > 0) +
            np.sum(border_edges_left > 0) + np.sum(border_edges_right > 0)
        ) / (border_edges_top.size + border_edges_bottom.size + border_edges_left.size + border_edges_right.size + 1e-10)
        
        # Product photo indicator: center has much more detail than borders
        is_product_photo_layout = center_edge_density > (border_edge_density * 2.5) and center_edge_density > 0.08
        
        # Method 5: Multi-scale blur detection (NEW)
        # Sharp images maintain detail across scales
        blur_3x3 = cv2.GaussianBlur(img_array, (3, 3), 0)
        blur_5x5 = cv2.GaussianBlur(img_array, (5, 5), 0)
        blur_7x7 = cv2.GaussianBlur(img_array, (7, 7), 0)
        detail_loss_3x3 = np.mean(np.abs(img_array.astype(np.float32) - blur_3x3.astype(np.float32)))
        detail_loss_5x5 = np.mean(np.abs(img_array.astype(np.float32) - blur_5x5.astype(np.float32)))
        detail_loss_7x7 = np.mean(np.abs(img_array.astype(np.float32) - blur_7x7.astype(np.float32)))
        
        # Detect motion blur (directional blur patterns)
        # Motion blur has low variance in one direction
        kernel_horizontal = np.ones((1, 9)) / 9
        kernel_vertical = np.ones((9, 1)) / 9
        h_blur_response = np.std(cv2.filter2D(img_array.astype(np.float32), -1, kernel_horizontal))
        v_blur_response = np.std(cv2.filter2D(img_array.astype(np.float32), -1, kernel_vertical))
        motion_blur_indicator = min(h_blur_response, v_blur_response) / (max(h_blur_response, v_blur_response) + 1e-10)
        is_motion_blurred = motion_blur_indicator < 0.7  # Directional blur detected
        
        # Method 6: Wavelet-based sharpness (NEW - ADVANCED)
        # Use difference of Gaussians to detect detail at multiple scales
        dog_1 = cv2.GaussianBlur(img_array, (3, 3), 0.5) - cv2.GaussianBlur(img_array, (3, 3), 1.0)
        dog_2 = cv2.GaussianBlur(img_array, (5, 5), 1.0) - cv2.GaussianBlur(img_array, (5, 5), 2.0)
        wavelet_energy = np.mean(np.abs(dog_1)) + np.mean(np.abs(dog_2))
        
        # Method 7: NOISE DETECTION - ENHANCED with multiple metrics
        # 7a. Local standard deviation (texture noise)
        kernel_size = 5
        mean_filtered = cv2.blur(img_array.astype(np.float32), (kernel_size, kernel_size))
        variance_map = cv2.blur((img_array.astype(np.float32) - mean_filtered)**2, (kernel_size, kernel_size))
        noise_score = np.mean(variance_map)
        
        # 7b. High-frequency noise in smooth regions
        blurred = cv2.GaussianBlur(img_array, (5, 5), 0)
        noise_map = np.abs(img_array.astype(np.float32) - blurred.astype(np.float32))
        high_freq_noise = np.mean(noise_map)
        
        # 7c. Signal-to-Noise Ratio estimation
        signal_strength = np.std(mean_filtered)
        noise_strength = np.mean(np.sqrt(variance_map))
        snr = signal_strength / (noise_strength + 1e-10)
        
        # 7d. Texture uniformity (noisy images lack consistent texture)
        # GLCM-inspired metric: consistency of local patterns
        kernel_3x3 = np.ones((3, 3)) / 9
        local_mean = cv2.filter2D(img_array.astype(np.float32), -1, kernel_3x3)
        local_variance = cv2.filter2D((img_array.astype(np.float32) - local_mean)**2, -1, kernel_3x3)
        texture_consistency = np.std(local_variance)
        
        # Method 8: Contrast and dynamic range (NEW)
        contrast = np.std(img_array)
        dynamic_range = np.max(img_array) - np.min(img_array)
        
        # BALANCED noise detection - catch real noise without false positives
        # Distinguish between texture/grain and problematic noise
        # Soft/lenient to avoid false positives on textured products
        is_noisy = (
            noise_score > 200 or  # Soft threshold - only extreme noise
            high_freq_noise > 11 or  # Soft threshold - only extreme noise
            snr < 3.5 or  # Soft threshold - only extremely poor signal
            (texture_consistency > 1200 and noise_score > 160)  # Soft combined check
        )
        
        # Calculate penalties for poor quality indicators (BALANCED)
        noise_penalty = 0
        if is_noisy:
            # Progressive penalty based on severity - SOFT/LENIENT
            if noise_score > 280 or high_freq_noise > 13 or snr < 2.5:
                noise_penalty = 30  # Severe noise - soft threshold
            elif noise_score > 230 or high_freq_noise > 12 or snr < 3.5:
                noise_penalty = 22  # High noise - soft threshold
            else:
                noise_penalty = 16  # Moderate noise
        
        # Low detail penalty - BALANCED - catch blurry images without false positives
        detail_penalty = 0
        if detail_loss_3x3 < 0.6:  # Severe lack of detail
            detail_penalty = 30  # BALANCED penalty
        elif detail_loss_3x3 < 1.2:  # Moderate lack of detail
            detail_penalty = 22  # BALANCED penalty
        elif detail_loss_3x3 < 2.0:  # Some lack of detail
            detail_penalty = 15
        elif wavelet_energy < 4:
            detail_penalty = 12
        
        # Motion blur penalty - BALANCED
        motion_blur_penalty = 0
        if is_motion_blurred:
            motion_blur_penalty = 25  # BALANCED penalty for motion blur
        
        # Severe blur penalty (very low Laplacian) - BALANCED
        severe_blur_penalty = 0
        if laplacian_var < 60:  # Extremely blurry
            severe_blur_penalty = 35  # BALANCED penalty
        elif laplacian_var < 150:  # Very blurry
            severe_blur_penalty = 25  # BALANCED penalty
        elif laplacian_var < 300:  # Moderate blur
            severe_blur_penalty = 16
        elif laplacian_var < 450:  # Subtle blur
            severe_blur_penalty = 10
        
        # Poor contrast penalty (BALANCED)
        contrast_penalty = 0
        if contrast < 25 or dynamic_range < 90:
            contrast_penalty = 6  # Very low contrast/flat image
        
        # Combined quality penalty - BALANCED
        # Catch poor quality without penalizing good images
        combined_quality_penalty = 0
        if is_noisy and laplacian_var < 180:  # Noisy + low sharpness - soft
            combined_quality_penalty = 18
        elif is_noisy and snr < 3.0:  # Noisy + poor SNR - soft
            combined_quality_penalty = 15
        elif is_noisy and laplacian_var < 320:  # Noisy + moderate sharpness - soft
            combined_quality_penalty = 10
        
        # BALANCED SCORING - Moderate thresholds
        # Normalize scores with BALANCED thresholds
        laplacian_normalized = min(laplacian_var / 300.0, 1.0)  # Balanced threshold
        laplacian_mean_norm = min(laplacian_mean / 8.5, 1.0)  # Balanced threshold
        
        tenengrad_normalized = min(tenengrad_score / 500.0, 1.0)  # Balanced threshold
        gradient_std_norm = min(gradient_std / 18.0, 1.0)  # Balanced threshold
        
        fft_normalized = min(high_freq_energy / 21.0, 1.0)  # Balanced threshold
        freq_ratio_norm = min(freq_ratio / 0.30, 1.0)  # Balanced threshold
        
        edge_normalized = min(edge_density / 0.08, 1.0)  # Balanced threshold
        edge_strength_norm = min(edge_strength_ratio / 0.30, 1.0)  # Balanced threshold
        
        detail_normalized = min(detail_loss_3x3 / 4.5, 1.0)  # Balanced threshold
        wavelet_normalized = min(wavelet_energy / 12.0, 1.0)  # Balanced threshold
        
        snr_normalized = min(snr / 10.0, 1.0)  # Balanced threshold
        contrast_normalized = min(contrast / 42.0, 1.0)  # Balanced threshold
        
        # WEIGHTED COMBINED SCORE with all features (0-100)
        combined_score = (
            laplacian_normalized * 22 +
            laplacian_mean_norm * 9 +
            tenengrad_normalized * 16 +
            gradient_std_norm * 8 +
            fft_normalized * 11 +
            freq_ratio_norm * 5 +
            edge_normalized * 10 +
            edge_strength_norm * 5 +
            detail_normalized * 6 +
            wavelet_normalized * 5 +
            snr_normalized * 2 +
            contrast_normalized * 1
        ) * 100
        
        # Apply ALL penalties (now includes combined quality penalty)
        combined_score = max(0, combined_score - noise_penalty - detail_penalty - motion_blur_penalty - severe_blur_penalty - contrast_penalty - combined_quality_penalty)
        
        # HARD REJECTION - BALANCED to catch real blur without false positives
        # Be lenient with product photos (concentrated detail in center)
        hard_reject = (
            laplacian_var < 60 or  # Extremely low sharpness (BALANCED)
            detail_loss_3x3 < 0.6 or  # Almost no detail (BALANCED)
            wavelet_energy < 6 or  # Very low detail energy (BALANCED)
            (is_motion_blurred and laplacian_var < 150) or  # Motion blur (BALANCED)
            (laplacian_var < 120 and detail_loss_3x3 < 1.2) or  # Combined low indicators (BALANCED)
            (laplacian_var < 240 and detail_loss_3x3 < 2.0 and not is_product_photo_layout) or  # Subtle combined (BALANCED)
            (edge_density < 0.020 and not is_product_photo_layout) or  # Very few edges (BALANCED)
            (edge_density < 0.04 and laplacian_var < 320 and not is_product_photo_layout) or  # Low edges (BALANCED)
            (is_noisy and laplacian_var < 130) or  # Noisy + low sharpness - soft
            snr < 1.2 or  # Extremely poor signal - soft
            (is_noisy and snr < 3.0 and laplacian_var < 200) or  # Noisy + poor SNR - soft
            (noise_score > 270 and laplacian_var < 300) or  # High noise - soft
            (tenengrad_score < 220 and laplacian_var < 320 and not is_product_photo_layout)  # Low gradient (BALANCED)
        )
        
        if hard_reject:
            combined_score = 0  # Force rejection
        
        # BALANCED THRESHOLDS:
        # < 72: Poor quality (REJECT)
        # 72-82: Borderline quality
        # 82+: Acceptable (good product photos)
        is_blurry = combined_score < 72
        is_borderline = 72 <= combined_score < 82
        
        # Calculate confidence (0.0 to 1.0) - lower score = higher blur confidence
        blur_confidence = max(0.0, min(1.0, (82 - combined_score) / 82)) if combined_score < 82 else 0.0
        
        # Determine failure reason with detailed diagnosis
        quality_issues = []
        if hard_reject:
            quality_issues.append("EXTREME BLUR/POOR QUALITY")
        if snr < 3:
            quality_issues.append("extremely poor signal quality")
        elif snr < 8:
            quality_issues.append("poor signal quality")
        if is_motion_blurred:
            quality_issues.append("motion blur detected")
        if laplacian_var < 60:
            quality_issues.append("extremely blurry")
        elif laplacian_var < 120:
            quality_issues.append("severely blurry")
        elif laplacian_var < 250:
            quality_issues.append("very blurry")
        elif laplacian_var < 400:
            quality_issues.append("blurry")
        if is_noisy:
            quality_issues.append("noisy/grainy")
        if detail_loss_3x3 < 0.8:
            quality_issues.append("severely lacks detail")
        elif detail_loss_3x3 < 1.5:
            quality_issues.append("lacks detail")
        if contrast < 30:
            quality_issues.append("low contrast")
        
        quality_issue = " and ".join(quality_issues) if quality_issues else "poor quality"
        
        details = {
            "combined_score": combined_score,
            "hard_reject": hard_reject,
            "is_product_photo_layout": is_product_photo_layout,
            "center_edge_density": center_edge_density,
            "border_edge_density": border_edge_density,
            "laplacian_var": laplacian_var,
            "laplacian_mean": laplacian_mean,
            "tenengrad_score": tenengrad_score,
            "gradient_std": gradient_std,
            "high_freq_energy": high_freq_energy,
            "freq_ratio": freq_ratio,
            "edge_density": edge_density,
            "strong_edge_density": strong_edge_density,
            "edge_strength_ratio": edge_strength_ratio,
            "detail_loss": detail_loss_3x3,
            "detail_loss_5x5": detail_loss_5x5,
            "detail_loss_7x7": detail_loss_7x7,
            "wavelet_energy": wavelet_energy,
            "motion_blur_indicator": motion_blur_indicator,
            "is_motion_blurred": is_motion_blurred,
            "noise_score": noise_score,
            "high_freq_noise": high_freq_noise,
            "snr": snr,
            "texture_consistency": texture_consistency,
            "contrast": contrast,
            "dynamic_range": dynamic_range,
            "is_noisy": is_noisy,
            "penalties": {
                "noise": noise_penalty,
                "detail": detail_penalty,
                "motion_blur": motion_blur_penalty,
                "severe_blur": severe_blur_penalty,
                "contrast": contrast_penalty,
                "combined_quality": combined_quality_penalty
            },
            "quality_grade": "poor" if is_blurry else "borderline" if is_borderline else "good",
            "confidence": blur_confidence
        }
        
        if is_blurry:
            reason_text = f"Image too {quality_issue} (score: {combined_score:.1f}/100)"
            if is_product_photo_layout:
                reason_text += " [Product layout]"
            return {
                "passed": False,
                "reason": reason_text,
                "details": details,
                "confidence": blur_confidence
            }
        
        reason_text = f"Image sharpness acceptable (score: {combined_score:.1f}/100)"
        if is_product_photo_layout:
            reason_text += " [Product layout]"
        return {
            "passed": True,
            "reason": reason_text,
            "details": details,
            "confidence": blur_confidence
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
        
        # Extremely strict threshold - only flag obvious UI screenshots
        # Physical product photos with ports/holes should NOT be flagged
        if edge_density > 0.30:  # More than 30% edges (extremely high)
            # Check for text-like patterns (screenshots usually have lots of text)
            # Use horizontal and vertical line detection
            horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
            vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
            horizontal_lines = cv2.morphologyEx(edges, cv2.MORPH_OPEN, horizontal_kernel)
            vertical_lines = cv2.morphologyEx(edges, cv2.MORPH_OPEN, vertical_kernel)
            
            line_density = (np.sum(horizontal_lines > 0) + np.sum(vertical_lines > 0)) / edges.size
            
            # Additional check: look for MANY rectangular regions
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            rectangular_contours = 0
            for contour in contours:
                perimeter = cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
                if len(approx) == 4:  # Rectangle
                    rectangular_contours += 1
            
            # Calculate confidence based on line density and rectangles
            screenshot_confidence = 0.0
            if line_density > 0.10 and rectangular_contours > 100:
                screenshot_confidence = min(1.0, (line_density / 0.15) * (rectangular_contours / 150))
            
            # Need HIGH line density (UI elements) AND MANY rectangles (>100)
            if line_density > 0.10 and rectangular_contours > 100:
                return {
                    "passed": False,
                    "reason": "Likely screenshot or UI element",
                    "details": {
                        "edge_density": edge_density,
                        "line_density": line_density,
                        "rectangles": rectangular_contours
                    },
                    "confidence": screenshot_confidence
                }
        
        return {
            "passed": True,
            "reason": "Not a screenshot",
            "details": {"edge_density": edge_density},
            "confidence": 0.0
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
